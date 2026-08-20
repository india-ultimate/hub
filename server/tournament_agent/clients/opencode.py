"""OpenCode Go chat client (OpenAI- and Anthropic-compatible endpoints)."""

from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings

from server.tournament_agent.catalog import AgentModel, get_model

HTTP_ERROR_STATUS = 400


@dataclass
class ChatCompletionResult:
    content: str | None
    tool_calls: list[dict[str, Any]]
    raw: dict[str, Any]
    finish_reason: str | None = None

    @property
    def tokens(self) -> tuple[int, int]:
        """(input, output) as the provider reported them; (0, 0) when it did not.

        chat.completions says prompt/completion, Anthropic and the Responses API
        both say input/output. Read off `raw` so every construction site gets this
        without having to remember to fill it in.
        """
        usage = self.raw.get("usage") or {}
        if not isinstance(usage, dict):
            return 0, 0

        def read(*names: str) -> int:
            for name in names:
                value = usage.get(name)
                if isinstance(value, int):
                    return value
            return 0

        return read("prompt_tokens", "input_tokens"), read("completion_tokens", "output_tokens")


@dataclass
class StreamChunk:
    """One item from `chat_stream`.

    `type="text"` carries an incremental delta; exactly one `type="result"`
    chunk is emitted last, carrying the assembled ChatCompletionResult.
    `type="ping"` means only that the provider has gone quiet — see
    `_with_idle_pings`.
    """

    type: str
    text: str = ""
    result: ChatCompletionResult | None = None


class OpenCodeGoError(Exception):
    def __init__(self, message: str, status: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        # Worth another attempt: rate limiting, a gateway hiccup, a dropped
        # connection. A 400 never is — the request itself is what it dislikes.
        self.retryable = retryable


TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500
# Three attempts covers the single-blip case without making staff wait through a
# real outage: with the backoff below, the worst case adds two seconds.
MAX_ATTEMPTS = 3
# Well inside the 60s that Fly's proxy allows a connection to stay silent.
IDLE_PING_SECONDS = 10.0
RETRY_BACKOFF_SECONDS = (0.5, 1.5)


def _transport_error(exc: Exception, timeout: float) -> OpenCodeGoError:
    """A timeout or a dropped connection. Always worth one more attempt."""
    if isinstance(exc, httpx.TimeoutException):
        return OpenCodeGoError(f"OpenCode Go timed out after {timeout}s", retryable=True)
    return OpenCodeGoError(f"OpenCode Go connection failed: {exc}", retryable=True)


def _status_error(status: int, body: str) -> OpenCodeGoError:
    return OpenCodeGoError(
        f"OpenCode Go error {status}: {body[:800]}",
        status=status,
        retryable=status == TOO_MANY_REQUESTS or status >= SERVER_ERROR,
    )


# "auto" lets the model answer in prose when a tool was needed; "required" makes it
# pick one. Not every model behind the gateway accepts the forced form — this used
# to be hardcoded to "auto" because it returned 400 for Kimi and DeepSeek, neither
# of which is in the allowlist any more.
TOOL_CHOICE_AUTO = "auto"
TOOL_CHOICE_REQUIRED = "required"

# Models observed rejecting a forced choice, learned at runtime rather than
# declared: the first 400 downgrades that model for the life of the process, so a
# gateway that starts supporting it needs no code change, and one that never did
# costs a single wasted request.
_NO_FORCED_TOOLS: set[str] = set()


def forced_tools_disabled_for(model_id: str) -> bool:
    return model_id in _NO_FORCED_TOOLS


def _effective_tool_choice(model: AgentModel, requested: str, tools: Any) -> str:
    if not tools or requested == TOOL_CHOICE_AUTO:
        return TOOL_CHOICE_AUTO
    if model.id in _NO_FORCED_TOOLS:
        return TOOL_CHOICE_AUTO
    if not bool(int(os.environ.get("OPENCODE_GO_FORCE_TOOLS", "1"))):
        return TOOL_CHOICE_AUTO
    return requested


def _looks_like_tool_choice_rejection(exc: OpenCodeGoError) -> bool:
    """A 400 on a request that forced a tool. Treated as "this model won't do that"."""
    return exc.status == HTTP_ERROR_STATUS


def to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize internal message dicts to OpenAI chat.completions shape."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "tool":
            item: dict[str, Any] = {
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id") or "",
                "content": str(msg.get("content") or ""),
            }
            if msg.get("name"):
                item["name"] = msg["name"]
            out.append(item)
            continue
        if role == "assistant" and msg.get("tool_calls"):
            formatted_calls = []
            for tc in msg["tool_calls"]:
                if "function" in tc:
                    formatted_calls.append(tc)
                else:
                    formatted_calls.append(
                        {
                            "id": tc.get("id") or "",
                            "type": "function",
                            "function": {
                                "name": tc.get("name") or "",
                                "arguments": tc.get("arguments")
                                if isinstance(tc.get("arguments"), str)
                                else json.dumps(tc.get("arguments") or {}),
                            },
                        }
                    )
            out.append(
                {
                    "role": "assistant",
                    "content": msg.get("content"),
                    "tool_calls": formatted_calls,
                }
            )
            continue
        out.append({"role": role, "content": msg.get("content") or ""})
    return out


def extract_tool_calls_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse tool calls from OpenAI-style message, including legacy/alternate shapes."""
    tool_calls: list[dict[str, Any]] = []
    raw_calls = message.get("tool_calls") or []
    for tc in raw_calls:
        fn = tc.get("function") or {}
        name = fn.get("name") or tc.get("name") or ""
        args = fn.get("arguments") if "function" in tc else tc.get("arguments")
        if args is None:
            args = tc.get("input") or {}
        if not isinstance(args, str):
            args = json.dumps(args)
        tool_calls.append({"id": tc.get("id") or "", "name": name, "arguments": args})

    # Legacy single function_call
    fc = message.get("function_call")
    if fc and isinstance(fc, dict) and fc.get("name"):
        args = fc.get("arguments") or "{}"
        if not isinstance(args, str):
            args = json.dumps(args)
        tool_calls.append({"id": "fncall_0", "name": fc["name"], "arguments": args})

    # Some models emit tool XML/JSON in content when native tools fail
    if not tool_calls and message.get("content"):
        tool_calls.extend(_parse_tool_calls_from_text(str(message["content"])))

    return [tc for tc in tool_calls if tc.get("name")]


_TOOL_CALL_JSON_RE = re.compile(
    r"\{\s*\"(?:name|tool)\"\s*:\s*\"([a-zA-Z0-9_]+)\"\s*,\s*\"(?:arguments|parameters|input)\"\s*:\s*(\{.*?\})\s*\}",
    re.DOTALL,
)
_INVOKE_RE = re.compile(
    r"<tool_call>\s*<name>(?P<name>[a-zA-Z0-9_]+)</name>\s*<arguments>(?P<args>\{.*?\})</arguments>\s*</tool_call>",
    re.DOTALL,
)


def _parse_tool_calls_from_text(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for i, m in enumerate(_INVOKE_RE.finditer(text)):
        found.append(
            {"id": f"text_tool_{i}", "name": m.group("name"), "arguments": m.group("args")}
        )
    if found:
        return found
    for i, m in enumerate(_TOOL_CALL_JSON_RE.finditer(text)):
        found.append({"id": f"text_json_{i}", "name": m.group(1), "arguments": m.group(2)})
    return found


def _responses_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for tool in tools or []:
        fn_raw = tool.get("function")
        fn: dict[str, Any] = fn_raw if isinstance(fn_raw, dict) else tool
        name = str(fn.get("name") or "")
        if not name:
            continue
        converted.append(
            {
                "type": "function",
                "name": name,
                "description": str(fn.get("description") or ""),
                "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return converted


def _tool_call_name_and_args(tc: dict[str, Any]) -> tuple[str, str]:
    if isinstance(tc.get("function"), dict):
        fn = tc["function"]
        name = str(fn.get("name") or "")
        args = fn.get("arguments")
    else:
        name = str(tc.get("name") or "")
        args = tc.get("arguments")
    if not isinstance(args, str):
        args = json.dumps(args or {})
    return name, args


def _responses_body(
    model: AgentModel,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    temperature: float | None,
    max_tokens: int,
    tool_choice: str = TOOL_CHOICE_AUTO,
) -> dict[str, Any]:
    instructions: list[str] = []
    input_items: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            instructions.append(str(msg.get("content") or ""))
            continue
        if role == "tool":
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": str(msg.get("tool_call_id") or ""),
                    "output": str(msg.get("content") or ""),
                }
            )
            continue
        if role == "assistant" and msg.get("tool_calls"):
            if msg.get("content"):
                input_items.append({"role": "assistant", "content": str(msg["content"])})
            for tc in msg["tool_calls"]:
                name, args = _tool_call_name_and_args(tc)
                input_items.append(
                    {
                        "type": "function_call",
                        "call_id": str(tc.get("id") or ""),
                        "name": name,
                        "arguments": args,
                    }
                )
            continue
        input_items.append({"role": role, "content": msg.get("content") or ""})

    body: dict[str, Any] = {
        "model": model.id,
        "input": input_items,
        "max_output_tokens": max_tokens,
    }
    if instructions:
        body["instructions"] = "\n\n".join(instructions)
    if temperature is not None:
        body["temperature"] = temperature
    converted = _responses_tools(tools)
    if converted:
        body["tools"] = converted
        body["tool_choice"] = tool_choice
    return body


def _parse_responses_result(data: dict[str, Any]) -> ChatCompletionResult:
    tool_calls: list[dict[str, Any]] = []
    texts: list[str] = []
    for item in data.get("output") or []:
        typ = item.get("type")
        if typ == "function_call":
            args = item.get("arguments")
            if not isinstance(args, str):
                args = json.dumps(args or {})
            tool_calls.append(
                {
                    "id": str(item.get("call_id") or item.get("id") or ""),
                    "name": str(item.get("name") or ""),
                    "arguments": args,
                }
            )
            continue
        if typ == "message":
            for part in item.get("content") or []:
                if part.get("type") in {"output_text", "text"} and part.get("text"):
                    texts.append(str(part["text"]))
    return ChatCompletionResult(
        content="\n".join(texts) or None,
        tool_calls=[tc for tc in tool_calls if tc.get("name")],
        raw=data,
        finish_reason=str(data.get("status") or data.get("finish_reason") or "") or None,
    )


def _with_idle_pings(chunks: Iterator[StreamChunk], interval: float) -> Iterator[StreamChunk]:
    """Pass `chunks` through, injecting a `ping` whenever the provider goes quiet.

    A reasoning model can spend well over a minute before its first token, and
    every hop in front of us gives up on a silent connection long before that —
    Fly's proxy at 60s. Something has to come down the wire in the meantime.

    The read runs on a helper thread so this generator can wake up on a timer
    instead of blocking on the socket. That thread deliberately touches nothing
    but httpx: the ORM, and so the caller's connection and transaction, stay on
    the caller's thread. The queue is unbounded so that a consumer who walks away
    lets the thread drain and exit rather than wedging it on a full queue.
    """
    out: queue.Queue[tuple[str, Any]] = queue.Queue()

    def read() -> None:
        try:
            for chunk in chunks:
                out.put(("chunk", chunk))
        except BaseException as exc:  # — re-raised on the consumer's thread
            out.put(("error", exc))
        finally:
            out.put(("end", None))

    thread = threading.Thread(target=read, name="opencode-stream", daemon=True)
    thread.start()
    while True:
        try:
            kind, item = out.get(timeout=interval)
        except queue.Empty:
            yield StreamChunk(type="ping")
            continue
        if kind == "chunk":
            yield item
        elif kind == "error":
            raise item
        else:
            return


class OpenCodeGoClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.OPENCODE_GO_API_KEY
        self.base_url = (base_url or settings.OPENCODE_GO_BASE_URL).rstrip("/")
        self.timeout = timeout

    def _resolve(
        self, model_id: str, temperature: float | None, max_tokens: int | None
    ) -> tuple[AgentModel, float | None, int]:
        model = get_model(model_id)
        if model is None:
            raise OpenCodeGoError(f"Model not allowed: {model_id}")
        if not self.api_key:
            raise OpenCodeGoError("OPENCODE_GO_API_KEY is not configured")

        temp = (
            temperature
            if temperature is not None
            else getattr(settings, "OPENCODE_GO_TEMPERATURE", None)
        )
        # OpenCode Go + tools is unreliable with temperature for some models (Kimi).
        # Only send temperature when explicitly configured to a usable value via
        # OPENCODE_GO_SEND_TEMPERATURE=1.
        if not bool(int(os.environ.get("OPENCODE_GO_SEND_TEMPERATURE", "0"))):
            temp = None
        tokens = max_tokens if max_tokens is not None else settings.OPENCODE_GO_MAX_TOKENS
        return model, temp, tokens

    def _dispatch_chat(
        self,
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temp: float | None,
        tokens: int,
        tool_choice: str,
    ) -> ChatCompletionResult:
        try:
            if model.api_style == "openai":
                return self._openai_chat(model, messages, tools, temp, tokens, tool_choice)
            if model.api_style == "responses":
                return self._responses_chat(model, messages, tools, temp, tokens, tool_choice)
            return self._anthropic_chat(model, messages, tools, temp, tokens, tool_choice)
        except httpx.HTTPError as exc:
            raise _transport_error(exc, self.timeout) from exc

    def _recover(
        self, exc: OpenCodeGoError, model: AgentModel, choice: str, attempt: int
    ) -> str | None:
        """The choice to retry with, or None when this error ends the turn.

        Two recoverable situations share one loop: a model that will not accept a
        forced tool (downgrade it, permanently), and a gateway that hiccuped
        (wait, try the same request again).
        """
        if choice != TOOL_CHOICE_AUTO and _looks_like_tool_choice_rejection(exc):
            _NO_FORCED_TOOLS.add(model.id)
            return TOOL_CHOICE_AUTO
        if exc.retryable and attempt + 1 < MAX_ATTEMPTS:
            time.sleep(RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)])
            return choice
        return None

    def chat(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> ChatCompletionResult:
        model, temp, tokens = self._resolve(model_id, temperature, max_tokens)
        choice = _effective_tool_choice(model, tool_choice, tools)
        for attempt in range(MAX_ATTEMPTS):
            try:
                return self._dispatch_chat(model, messages, tools, temp, tokens, choice)
            except OpenCodeGoError as exc:
                recovered = self._recover(exc, model, choice, attempt)
                if recovered is None:
                    raise
                choice = recovered
        raise OpenCodeGoError("Exhausted retries without a result")

    def chat_stream(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> Iterator[StreamChunk]:
        """Same contract as `chat`, but yields text deltas before the result."""
        model, temp, tokens = self._resolve(model_id, temperature, max_tokens)
        choice = _effective_tool_choice(model, tool_choice, tools)
        for attempt in range(MAX_ATTEMPTS):
            emitted = False
            try:
                stream = self._stream_once(model, messages, tools, temp, tokens, choice)
                for chunk in _with_idle_pings(stream, IDLE_PING_SECONDS):
                    # A ping is not the provider answering, so it must not make the
                    # attempt look committed — a failure after one is still retryable.
                    if chunk.type == "ping":
                        yield chunk
                        continue
                    emitted = True
                    yield chunk
                return
            except OpenCodeGoError as exc:
                # Only safe to retry while nothing has reached the browser. The
                # status check happens before the first chunk, so the common
                # failures land here with nothing emitted.
                if emitted:
                    raise
                recovered = self._recover(exc, model, choice, attempt)
                if recovered is None:
                    raise
                choice = recovered

    def _stream_once(
        self,
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temp: float | None,
        tokens: int,
        tool_choice: str,
    ) -> Iterator[StreamChunk]:
        try:
            if model.api_style == "openai":
                yield from self._openai_chat_stream(
                    model, messages, tools, temp, tokens, tool_choice
                )
            elif model.api_style == "responses":
                result = self._responses_chat(model, messages, tools, temp, tokens, tool_choice)
                if result.content:
                    yield StreamChunk(type="text", text=result.content)
                yield StreamChunk(type="result", result=result)
            else:
                yield from self._anthropic_chat_stream(
                    model, messages, tools, temp, tokens, tool_choice
                )
        except httpx.HTTPError as exc:
            raise _transport_error(exc, self.timeout) from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _sse_payloads(resp: httpx.Response) -> Iterator[dict[str, Any]]:
        """Yield decoded JSON payloads from an SSE body, skipping comments/[DONE]."""
        for raw_line in resp.iter_lines():
            line = raw_line.strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                return
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload

    @staticmethod
    def _raise_for_stream_status(resp: httpx.Response) -> None:
        if resp.status_code >= HTTP_ERROR_STATUS:
            body = resp.read().decode(resp.encoding or "utf-8", errors="replace")
            raise _status_error(resp.status_code, body)

    @staticmethod
    def _openai_body(
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int,
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model.id,
            "messages": to_openai_messages(messages),
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice
        return body

    def _openai_chat(
        self,
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int,
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> ChatCompletionResult:
        body = self._openai_body(model, messages, tools, temperature, max_tokens, tool_choice)

        url = f"{self.base_url}/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self._headers(), json=body)
        if resp.status_code >= HTTP_ERROR_STATUS:
            raise _status_error(resp.status_code, resp.text)
        data = resp.json()
        if data.get("error"):
            raise OpenCodeGoError(f"OpenCode Go API error: {data['error']}")

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = extract_tool_calls_from_message(message)
        content = message.get("content")
        # If we recovered tools from text, strip raw dump from user-visible content
        if tool_calls and content and "<tool_call>" in content:
            content = _INVOKE_RE.sub("", content).strip() or None

        return ChatCompletionResult(
            content=content,
            tool_calls=tool_calls,
            raw=data,
            finish_reason=choice.get("finish_reason"),
        )

    def _responses_chat(
        self,
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int,
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> ChatCompletionResult:
        # GPT-5.6 Luna (and Grok on Go) speak the OpenAI Responses API, not
        # chat.completions. Keep the internal ChatCompletionResult contract.
        body = _responses_body(model, messages, tools, temperature, max_tokens, tool_choice)
        url = f"{self.base_url}/responses"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self._headers(), json=body)
        if resp.status_code >= HTTP_ERROR_STATUS:
            raise _status_error(resp.status_code, resp.text)
        data = resp.json()
        if data.get("error"):
            raise OpenCodeGoError(f"OpenCode Go API error: {data['error']}")
        return _parse_responses_result(data)

    @staticmethod
    def _anthropic_body(
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int,
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> dict[str, Any]:
        system_parts: list[str] = []
        anth_messages: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                system_parts.append(str(msg.get("content") or ""))
                continue
            if role == "tool":
                anth_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id") or "",
                                "content": str(msg.get("content") or ""),
                            }
                        ],
                    }
                )
                continue
            if role == "assistant" and msg.get("tool_calls"):
                content_blocks: list[dict[str, Any]] = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    args = tc.get("arguments") or "{}"
                    if isinstance(args, str):
                        try:
                            args_obj = json.loads(args)
                        except json.JSONDecodeError:
                            args_obj = {"raw": args}
                    else:
                        args_obj = args
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id") or "",
                            "name": tc.get("name") or "",
                            "input": args_obj,
                        }
                    )
                anth_messages.append({"role": "assistant", "content": content_blocks})
                continue
            anth_messages.append(
                {
                    "role": "user" if role == "user" else "assistant",
                    "content": msg.get("content") or "",
                }
            )

        body: dict[str, Any] = {
            "model": model.id,
            "messages": anth_messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        if tools:
            body["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description") or "",
                    "input_schema": t["function"].get("parameters")
                    or {"type": "object", "properties": {}},
                }
                for t in tools
                if t.get("type") == "function" and t.get("function")
            ]
            # Anthropic spells "pick something" as {"type": "any"}.
            body["tool_choice"] = {"type": "any" if tool_choice == TOOL_CHOICE_REQUIRED else "auto"}
        return body

    def _anthropic_headers(self) -> dict[str, str]:
        # Anthropic-compatible Go models expect x-api-key (Bearer alone is ignored).
        return {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key or "",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

    def _anthropic_chat(
        self,
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int,
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> ChatCompletionResult:
        body = self._anthropic_body(model, messages, tools, temperature, max_tokens, tool_choice)
        url = f"{self.base_url}/messages"
        headers = self._anthropic_headers()
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=body)
        if resp.status_code >= HTTP_ERROR_STATUS:
            raise _status_error(resp.status_code, resp.text)
        data = resp.json()
        content_blocks = data.get("content") or []
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id") or "",
                        "name": block.get("name") or "",
                        "arguments": json.dumps(block.get("input") or {}),
                    }
                )
        content = "\n".join(text_parts) if text_parts else None
        if not tool_calls and content:
            tool_calls = _parse_tool_calls_from_text(content)

        return ChatCompletionResult(
            content=content,
            tool_calls=tool_calls,
            raw=data,
            finish_reason=data.get("stop_reason"),
        )

    def _openai_chat_stream(
        self,
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int,
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> Iterator[StreamChunk]:
        body = self._openai_body(model, messages, tools, temperature, max_tokens, tool_choice)
        body["stream"] = True

        url = f"{self.base_url}/chat/completions"
        text_parts: list[str] = []
        # Tool calls arrive as fragments keyed by index; name/arguments accrue over deltas.
        acc: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None

        with (
            httpx.Client(timeout=self.timeout) as client,
            client.stream("POST", url, headers=self._headers(), json=body) as resp,
        ):
            self._raise_for_stream_status(resp)
            for payload in self._sse_payloads(resp):
                if payload.get("error"):
                    raise OpenCodeGoError(f"OpenCode Go API error: {payload['error']}")
                choice = (payload.get("choices") or [{}])[0]
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta") or {}
                piece = delta.get("content")
                if piece:
                    text_parts.append(str(piece))
                    yield StreamChunk(type="text", text=str(piece))
                for tc in delta.get("tool_calls") or []:
                    idx = int(tc.get("index") or 0)
                    slot = acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = str(tc["id"])
                    fn = tc.get("function") or {}
                    # Spec sends the name once and streams only arguments, but not
                    # every model behind OpenCode Go conforms. Appending is a no-op
                    # for the conforming case and survives a name split over deltas.
                    if fn.get("name"):
                        slot["name"] += str(fn["name"])
                    if fn.get("arguments"):
                        slot["arguments"] += str(fn["arguments"])

        content: str | None = "".join(text_parts) or None
        tool_calls = [
            {"id": slot["id"], "name": slot["name"], "arguments": slot["arguments"] or "{}"}
            for _, slot in sorted(acc.items())
            if slot["name"]
        ]
        if not tool_calls and content:
            tool_calls = _parse_tool_calls_from_text(content)
        if tool_calls and content and "<tool_call>" in content:
            content = _INVOKE_RE.sub("", content).strip() or None

        raw = {"streamed": True, "finish_reason": finish_reason}
        yield StreamChunk(
            type="result",
            result=ChatCompletionResult(
                content=content,
                tool_calls=tool_calls,
                raw=raw,
                finish_reason=finish_reason,
            ),
        )

    def _anthropic_chat_stream(
        self,
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int,
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> Iterator[StreamChunk]:
        body = self._anthropic_body(model, messages, tools, temperature, max_tokens, tool_choice)
        body["stream"] = True

        url = f"{self.base_url}/messages"
        text_parts: list[str] = []
        # content_block_start announces each block; deltas then stream into it by index.
        blocks: dict[int, dict[str, str]] = {}
        stop_reason: str | None = None

        with (
            httpx.Client(timeout=self.timeout) as client,
            client.stream("POST", url, headers=self._anthropic_headers(), json=body) as resp,
        ):
            self._raise_for_stream_status(resp)
            for payload in self._sse_payloads(resp):
                kind = payload.get("type")
                if kind == "error":
                    raise OpenCodeGoError(f"OpenCode Go API error: {payload.get('error')}")
                if kind == "content_block_start":
                    idx = int(payload.get("index") or 0)
                    block = payload.get("content_block") or {}
                    blocks[idx] = {
                        "type": str(block.get("type") or ""),
                        "id": str(block.get("id") or ""),
                        "name": str(block.get("name") or ""),
                        "json": "",
                    }
                elif kind == "content_block_delta":
                    idx = int(payload.get("index") or 0)
                    delta = payload.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        piece = str(delta.get("text") or "")
                        if piece:
                            text_parts.append(piece)
                            yield StreamChunk(type="text", text=piece)
                    elif delta.get("type") == "input_json_delta":
                        slot = blocks.setdefault(
                            idx, {"type": "tool_use", "id": "", "name": "", "json": ""}
                        )
                        slot["json"] += str(delta.get("partial_json") or "")
                elif kind == "message_delta":
                    stop_reason = (payload.get("delta") or {}).get("stop_reason") or stop_reason

        content: str | None = "".join(text_parts) or None
        tool_calls = [
            {"id": slot["id"], "name": slot["name"], "arguments": slot["json"] or "{}"}
            for _, slot in sorted(blocks.items())
            if slot["type"] == "tool_use" and slot["name"]
        ]
        if not tool_calls and content:
            tool_calls = _parse_tool_calls_from_text(content)
        if tool_calls and content and "<tool_call>" in content:
            content = _INVOKE_RE.sub("", content).strip() or None

        raw = {"streamed": True, "stop_reason": stop_reason}
        yield StreamChunk(
            type="result",
            result=ChatCompletionResult(
                content=content,
                tool_calls=tool_calls,
                raw=raw,
                finish_reason=stop_reason,
            ),
        )

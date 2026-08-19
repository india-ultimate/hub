"""OpenCode Go chat client (OpenAI- and Anthropic-compatible endpoints)."""

from __future__ import annotations

import json
import os
import re
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


@dataclass
class StreamChunk:
    """One item from `chat_stream`.

    `type="text"` carries an incremental delta; exactly one `type="result"`
    chunk is emitted last, carrying the assembled ChatCompletionResult.
    """

    type: str
    text: str = ""
    result: ChatCompletionResult | None = None


class OpenCodeGoError(Exception):
    pass


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
        body["tool_choice"] = "auto"
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

    def chat(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletionResult:
        model, temp, tokens = self._resolve(model_id, temperature, max_tokens)
        if model.api_style == "openai":
            return self._openai_chat(model, messages, tools, temp, tokens)
        if model.api_style == "responses":
            return self._responses_chat(model, messages, tools, temp, tokens)
        return self._anthropic_chat(model, messages, tools, temp, tokens)

    def chat_stream(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[StreamChunk]:
        """Same contract as `chat`, but yields text deltas before the result."""
        model, temp, tokens = self._resolve(model_id, temperature, max_tokens)
        if model.api_style == "openai":
            yield from self._openai_chat_stream(model, messages, tools, temp, tokens)
        elif model.api_style == "responses":
            result = self._responses_chat(model, messages, tools, temp, tokens)
            if result.content:
                yield StreamChunk(type="text", text=result.content)
            yield StreamChunk(type="result", result=result)
        else:
            yield from self._anthropic_chat_stream(model, messages, tools, temp, tokens)

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
            raise OpenCodeGoError(f"OpenCode Go error {resp.status_code}: {body[:800]}")

    @staticmethod
    def _openai_body(
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int,
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
            # Only "auto" is reliably supported across Go models with tools;
            # "required" / forced-function returns 400 for Kimi and DeepSeek.
            body["tool_choice"] = "auto"
        return body

    def _openai_chat(
        self,
        model: AgentModel,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int,
    ) -> ChatCompletionResult:
        body = self._openai_body(model, messages, tools, temperature, max_tokens)

        url = f"{self.base_url}/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self._headers(), json=body)
        if resp.status_code >= HTTP_ERROR_STATUS:
            raise OpenCodeGoError(f"OpenCode Go error {resp.status_code}: {resp.text[:800]}")
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
    ) -> ChatCompletionResult:
        # GPT-5.6 Luna (and Grok on Go) speak the OpenAI Responses API, not
        # chat.completions. Keep the internal ChatCompletionResult contract.
        body = _responses_body(model, messages, tools, temperature, max_tokens)
        url = f"{self.base_url}/responses"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self._headers(), json=body)
        if resp.status_code >= HTTP_ERROR_STATUS:
            raise OpenCodeGoError(f"OpenCode Go error {resp.status_code}: {resp.text[:800]}")
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
    ) -> ChatCompletionResult:
        body = self._anthropic_body(model, messages, tools, temperature, max_tokens)
        url = f"{self.base_url}/messages"
        headers = self._anthropic_headers()
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=body)
        if resp.status_code >= HTTP_ERROR_STATUS:
            raise OpenCodeGoError(f"OpenCode Go error {resp.status_code}: {resp.text[:800]}")
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
    ) -> Iterator[StreamChunk]:
        body = self._openai_body(model, messages, tools, temperature, max_tokens)
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
    ) -> Iterator[StreamChunk]:
        body = self._anthropic_body(model, messages, tools, temperature, max_tokens)
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

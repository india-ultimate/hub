"""Tournament agent service: tool loop with PII masking and propose/confirm."""

from __future__ import annotations

import json
import time
from collections.abc import Generator, Iterator
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from server.core.models import User
from server.tournament.models import Tournament
from server.tournament_agent.catalog import default_model_id, is_allowed_model
from server.tournament_agent.mask import scrub_user_text
from server.tournament_agent.models import (
    AgentProposal,
    AgentQuestion,
    MessageKind,
    MessageRole,
    QuestionSelectionMode,
    QuestionStatus,
    TournamentAgentMessage,
    TournamentAgentSession,
)
from server.tournament_agent.provider import (
    ChatCompletionResult,
    OpenCodeGoClient,
    OpenCodeGoError,
)
from server.tournament_agent.tools import TOOL_DEFINITIONS, AskUserPause, ToolContext, dispatch_tool

SKILL_PATH = Path(__file__).parent / "skills" / "schedule_orchestration.md"


def _load_skill() -> str:
    try:
        return SKILL_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


SYSTEM_PROMPT = """You are the Tournament Manager AI Agent for India Ultimate Hub.
You help staff design pools, Swiss groups, brackets, schedules, and orchestrate tournaments.

Hard rules (non-negotiable):
1. You MUST use tools for every staff request that needs tournament data or changes. Do not answer from memory alone.
2. Never invent personal data. You only see allowlisted tournament ops fields (teams, seeds, matches, fields, times).
3. Ambiguous setup requests ("set up the tournament", "configure this", "make pools or swiss") REQUIRE calling ask_user BEFORE any propose_* tool. Offer clear options (e.g. pools vs Swiss).
4. Never mutate the database yourself. Use propose_* tools; staff must Confirm proposals in the UI.
5. Schedule requests ("recommend a schedule", "schedule Saturday") REQUIRE calling propose_recommended_schedule after checking fields/matches with read tools if needed.
6. Be concise. Use markdown in final replies only after tools have been used.

Examples:
- User: "Set up this tournament for me"
  → call ask_user with selection_mode=single and options for pools vs Swiss (and optionally duration).
- User: "Recommend a schedule for Saturday starting 2026-08-01 with 75 minute games"
  → call list_fields and/or list_matches, then propose_recommended_schedule with start_date and duration_mins=75.

""" + _load_skill()


MAX_EVENT_ARGS_CHARS = 4000


def _tool_event_args(args: dict[str, Any]) -> dict[str, Any]:
    """Arguments as stored on the tool event; oversized payloads get truncated."""
    try:
        raw = json.dumps(args)
    except (TypeError, ValueError):
        return {"_unserializable": True}
    if len(raw) > MAX_EVENT_ARGS_CHARS:
        return {"_truncated": True, "preview": raw[:MAX_EVENT_ARGS_CHARS]}
    return args


def _summarize_tool_result(name: str, result: Any) -> str:
    """One-line human summary of a tool result for the UI timeline."""
    if not isinstance(result, dict):
        return ""
    if result.get("error"):
        return str(result["error"])[:200]
    if result.get("proposal_id"):
        summary = str(result.get("summary") or "Proposal created")
        return f"Proposal #{result['proposal_id']}: {summary}"[:200]
    for key, value in result.items():
        if isinstance(value, list):
            return f"{len(value)} {key.replace('_', ' ')}"
    if name == "get_tournament_overview":
        return (
            f"{result.get('team_count', '?')} teams, {result.get('match_count', '?')} matches, "
            f"{result.get('unscheduled_match_count', '?')} unscheduled"
        )
    keys = ", ".join(list(result.keys())[:6])
    return keys[:200]


class TournamentAgentService:
    def __init__(
        self,
        user: User,
        client: OpenCodeGoClient | None = None,
        streaming: bool = False,
    ) -> None:
        self.user = user
        self.client = client or OpenCodeGoClient()
        self.max_tool_rounds = 8
        self.last_trace: list[dict[str, Any]] = []
        self.force_tool_choice: str | dict[str, Any] | None = "auto"
        self.case_hint: str = ""
        # When on, model text is pulled via chat_stream and re-emitted as text_delta
        # events. Off (the default) keeps the single-shot chat() call, so callers and
        # tests that never opted into streaming behave exactly as before.
        self.streaming = streaming

    def get_or_create_session(
        self, tournament_id: int, model_id: str | None = None
    ) -> TournamentAgentSession:
        if not self.user.is_staff:
            raise PermissionError("Staff only")
        tournament = Tournament.objects.get(id=tournament_id)
        mid = model_id or settings.OPENCODE_GO_DEFAULT_MODEL or default_model_id()
        if not is_allowed_model(mid):
            raise ValueError(f"Model not allowed: {mid}")
        session, created = TournamentAgentSession.objects.get_or_create(
            user=self.user,
            tournament=tournament,
            defaults={"model_id": mid},
        )
        if not created and model_id and model_id != session.model_id:
            if not is_allowed_model(model_id):
                raise ValueError(f"Model not allowed: {model_id}")
            session.model_id = model_id
            session.save(update_fields=["model_id", "updated_at"])
        return session

    def set_model(self, session: TournamentAgentSession, model_id: str) -> TournamentAgentSession:
        if not is_allowed_model(model_id):
            raise ValueError(f"Model not allowed: {model_id}")
        session.model_id = model_id
        session.save(update_fields=["model_id", "updated_at"])
        return session

    def clear_session(self, session: TournamentAgentSession) -> None:
        session.messages.all().delete()
        session.questions.all().delete()
        # Leave proposals for audit; mark pending as expired? keep them.
        session.updated_at = timezone.now()
        session.save(update_fields=["updated_at"])

    def history(self, session: TournamentAgentSession) -> dict[str, Any]:
        messages = []
        for m in session.messages.all():
            item: dict[str, Any] = {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "message_kind": m.message_kind,
                "payload": m.payload or {},
                "model_id": m.model_id,
                "created_at": m.created_at.isoformat(),
            }
            messages.append(item)
        pending_q = (
            session.questions.filter(status=QuestionStatus.PENDING).order_by("-created_at").first()
        )
        return {
            "session_id": session.id,
            "tournament_id": session.tournament_id,
            "model_id": session.model_id,
            "messages": messages,
            "pending_question": self._serialize_question(pending_q) if pending_q else None,
            "pending_proposals": self._pending_proposals(session),
        }

    def _serialize_question(self, q: AgentQuestion) -> dict[str, Any]:
        return {
            "id": q.id,
            "prompt": q.prompt,
            "context": q.context,
            "selection_mode": q.selection_mode,
            "options": q.options,
            "allow_other": q.allow_other,
            "allow_skip": q.allow_skip,
            "status": q.status,
            "answer": q.answer,
        }

    def process_message(
        self, session: TournamentAgentSession, message: str
    ) -> dict[str, Any]:
        display = message
        masked = scrub_user_text(message)
        TournamentAgentMessage.objects.create(
            session=session,
            role=MessageRole.USER,
            content=display,
            message_kind=MessageKind.TEXT,
            payload={"masked_content": masked},
        )
        return self._run_agent(session, user_content_for_model=masked)

    def answer_question(
        self,
        session: TournamentAgentSession,
        question_id: int,
        selected_ids: list[str],
        other_text: str | None = None,
        skip: bool = False,
    ) -> dict[str, Any]:
        model_text = self._record_answer(
            session, question_id, selected_ids, other_text=other_text, skip=skip
        )
        return self._run_agent(session, user_content_for_model=model_text)

    def _record_answer(
        self,
        session: TournamentAgentSession,
        question_id: int,
        selected_ids: list[str],
        other_text: str | None = None,
        skip: bool = False,
    ) -> str:
        """Validate and persist a question answer; returns the text handed to the model."""
        try:
            question = AgentQuestion.objects.get(id=question_id, session=session)
        except AgentQuestion.DoesNotExist as exc:
            raise ValueError("Question not found") from exc
        if question.status != QuestionStatus.PENDING:
            raise ValueError("Question is not pending")

        if skip:
            # Staff can always cancel a pending question from the UI (not only when
            # the model set allow_skip). This dismisses stuck clarifying cards.
            question.status = QuestionStatus.SKIPPED
            question.answer = {"skipped": True, "cancelled": True}
            question.answered_at = timezone.now()
            question.save()
            answer_text = "User cancelled the clarifying question."
            TournamentAgentMessage.objects.create(
                session=session,
                role=MessageRole.USER,
                content=answer_text,
                message_kind=MessageKind.ANSWER,
                payload={"question_id": question.id, "skipped": True, "cancelled": True},
            )
            return answer_text

        selected_ids = [str(x) for x in selected_ids]
        option_ids = {str(o["id"]) for o in question.options}
        if any(sid not in option_ids for sid in selected_ids):
            raise ValueError("Invalid option id")
        if question.selection_mode == QuestionSelectionMode.SINGLE and len(selected_ids) != 1:
            if not (question.allow_other and other_text and not selected_ids):
                raise ValueError("Single select requires exactly one option")
        if question.selection_mode == QuestionSelectionMode.MULTI and not selected_ids and not (
            question.allow_other and other_text
        ):
            raise ValueError("Multi select requires at least one option")

        labels = []
        for opt in question.options:
            if str(opt["id"]) in selected_ids:
                labels.append(opt["label"])
        other_scrubbed = scrub_user_text(other_text) if other_text else None
        question.status = QuestionStatus.ANSWERED
        question.answer = {
            "selected_ids": selected_ids,
            "other_text": other_scrubbed,
        }
        question.answered_at = timezone.now()
        question.save()

        display = "Selected: " + ", ".join(labels)
        if other_text:
            display += f" | Other: {other_text}"
        model_text = (
            f"User answered question {question.id}: selected_ids={selected_ids}, "
            f"labels={labels}"
            + (f", other={other_scrubbed}" if other_scrubbed else "")
        )
        TournamentAgentMessage.objects.create(
            session=session,
            role=MessageRole.USER,
            content=display,
            message_kind=MessageKind.ANSWER,
            payload={
                "question_id": question.id,
                "selected_ids": selected_ids,
                "other_text": other_scrubbed,
            },
        )
        return model_text

    def _build_model_messages(self, session: TournamentAgentSession) -> list[dict[str, Any]]:
        system = SYSTEM_PROMPT
        if self.case_hint:
            system = system + "\n\nEval / case guidance:\n" + self.case_hint
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in session.messages.all():
            if m.role == MessageRole.USER:
                content = (m.payload or {}).get("masked_content") or scrub_user_text(m.content)
                messages.append({"role": "user", "content": content})
            elif m.role == MessageRole.ASSISTANT:
                messages.append({"role": "assistant", "content": m.content or ""})
        return messages

    def _chat_round(
        self,
        session: TournamentAgentSession,
        messages: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] | None,
    ) -> Generator[dict[str, Any], None, ChatCompletionResult]:
        """One model call. Yields text_delta events; returns the assembled result."""
        if not self.streaming:
            return self.client.chat(
                model_id=session.model_id,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice=tool_choice,
            )

        streamed: list[str] = []
        result: ChatCompletionResult | None = None
        for chunk in self.client.chat_stream(
            model_id=session.model_id,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice=tool_choice,
        ):
            if chunk.type == "text" and chunk.text:
                streamed.append(chunk.text)
                yield {"type": "text_delta", "text": chunk.text}
            elif chunk.type == "result":
                result = chunk.result
        if result is None:
            raise OpenCodeGoError("Stream ended without a result")
        # Models that emit tool calls as text get that text stripped from the reply.
        # The raw blob was already streamed, so correct what the client is showing.
        raw_streamed = "".join(streamed)
        if raw_streamed and (result.content or "") != raw_streamed:
            yield {"type": "text_replace", "text": result.content or ""}
        return result

    def _run_agent(
        self, session: TournamentAgentSession, user_content_for_model: str
    ) -> dict[str, Any]:
        """Drain the event stream and return only the final payload."""
        payload: dict[str, Any] = {}
        for event in self._run_agent_events(session, user_content_for_model):
            if event["type"] == "done":
                payload = event["payload"]
        return payload

    def _run_agent_events(
        self, session: TournamentAgentSession, user_content_for_model: str
    ) -> Iterator[dict[str, Any]]:
        messages = self._build_model_messages(session)
        _ = user_content_for_model

        self.last_trace = []
        pending_question = None
        final_text = ""
        assistant_msg: TournamentAgentMessage | None = None
        tool_choice: str | dict[str, Any] | None = self.force_tool_choice
        turn_tool_events: list[dict[str, Any]] = []

        def persist_tool_events() -> None:
            if assistant_msg is not None and turn_tool_events:
                assistant_msg.payload = {
                    **(assistant_msg.payload or {}),
                    "tool_events": turn_tool_events,
                }
                assistant_msg.save(update_fields=["payload"])

        try:
            for round_i in range(self.max_tool_rounds):
                try:
                    result = yield from self._chat_round(session, messages, tool_choice)
                except OpenCodeGoError as exc:
                    # Some Go models reject tool_choice=required; fall back once.
                    if tool_choice == "required":
                        self.last_trace.append(
                            {"warning": f"tool_choice=required failed: {exc}; retrying auto"}
                        )
                        tool_choice = "auto"
                        result = yield from self._chat_round(session, messages, "auto")
                    else:
                        raise
                self.last_trace.append(
                    {
                        "round": round_i,
                        "finish_reason": result.finish_reason,
                        "content_preview": (result.content or "")[:300],
                        "tool_calls": [
                            {"name": tc.get("name"), "id": tc.get("id")}
                            for tc in result.tool_calls
                        ],
                    }
                )

                if result.tool_calls:
                    # After the first tool round, let the model decide freely
                    tool_choice = "auto"
                    if assistant_msg is None:
                        assistant_msg = TournamentAgentMessage.objects.create(
                            session=session,
                            role=MessageRole.ASSISTANT,
                            content=result.content or "",
                            message_kind=MessageKind.TEXT,
                            model_id=session.model_id,
                        )
                    elif result.content:
                        assistant_msg.content = (assistant_msg.content or "") + (
                            "\n" + result.content if assistant_msg.content else result.content
                        )
                        assistant_msg.save(update_fields=["content"])

                    messages.append(
                        {
                            "role": "assistant",
                            "content": result.content,
                            "tool_calls": result.tool_calls,
                        }
                    )
                    ctx = ToolContext(
                        session=session,
                        tournament=session.tournament,
                        assistant_message=assistant_msg,
                    )
                    called_names = [tc["name"] for tc in result.tool_calls]
                    for tc in result.tool_calls:
                        name = tc["name"]
                        try:
                            args = json.loads(tc["arguments"] or "{}")
                            if not isinstance(args, dict):
                                args = {}
                        except json.JSONDecodeError:
                            args = {}
                        self.last_trace.append({"tool": name, "args_keys": list(args.keys())})
                        event: dict[str, Any] = {
                            "name": name,
                            "arguments": _tool_event_args(args),
                            "status": "ok",
                            "summary": "",
                        }
                        event_index = len(turn_tool_events)
                        yield {
                            "type": "tool_start",
                            "index": event_index,
                            "name": name,
                            "arguments": event["arguments"],
                        }
                        started_at = time.monotonic()
                        try:
                            tool_result = dispatch_tool(ctx, name, args)
                        except AskUserPause as pause:
                            pending_question = pause.question
                            event["status"] = "question"
                            event["summary"] = pause.question.prompt[:200]
                            event["duration_ms"] = int((time.monotonic() - started_at) * 1000)
                            turn_tool_events.append(event)
                            yield {"type": "tool_end", "index": event_index, **event}
                            assistant_msg.message_kind = MessageKind.QUESTION
                            assistant_msg.payload = {
                                **(assistant_msg.payload or {}),
                                "question_id": pause.question.id,
                            }
                            if not assistant_msg.content:
                                assistant_msg.content = pause.question.prompt
                            assistant_msg.save()
                            persist_tool_events()
                            messages.append(
                                {
                                    "role": "tool",
                                    "name": name,
                                    "tool_call_id": tc["id"],
                                    "content": json.dumps(
                                        {
                                            "question_id": pause.question.id,
                                            "status": "pending",
                                            "message": "Waiting for user answer",
                                        }
                                    ),
                                }
                            )
                            question_payload = self._serialize_question(pending_question)
                            yield {"type": "question", "question": question_payload}
                            yield {
                                "type": "done",
                                "payload": {
                                    "response": assistant_msg.content,
                                    "pending_question": question_payload,
                                    "pending_proposals": self._pending_proposals(session),
                                    "session_id": session.id,
                                    "model_id": session.model_id,
                                    "message_id": assistant_msg.id,
                                    "tool_events": turn_tool_events,
                                    "trace": self.last_trace,
                                },
                            }
                            return
                        except Exception as exc:  # noqa: BLE001 — model must see and recover from tool errors
                            tool_result = {"error": str(exc)[:500]}
                            event["status"] = "error"
                            event["summary"] = str(exc)[:200]
                            self.last_trace.append({"tool": name, "error": str(exc)[:200]})
                        event["duration_ms"] = int((time.monotonic() - started_at) * 1000)
                        if not event["summary"]:
                            if isinstance(tool_result, dict) and tool_result.get("proposal_id"):
                                event["status"] = "proposal"
                                event["proposal_id"] = tool_result["proposal_id"]
                            event["summary"] = _summarize_tool_result(name, tool_result)
                        turn_tool_events.append(event)
                        persist_tool_events()
                        yield {"type": "tool_end", "index": event_index, **event}
                        if event.get("proposal_id"):
                            proposal = self._serialize_proposal_by_id(
                                session, int(event["proposal_id"])
                            )
                            if proposal:
                                yield {"type": "proposal", "proposal": proposal}
                        messages.append(
                            {
                                "role": "tool",
                                "name": name,
                                "tool_call_id": tc["id"],
                                "content": json.dumps(tool_result),
                            }
                        )

                    # If the model only gathered context, nudge toward the action tool once.
                    read_only = {
                        "get_tournament_overview",
                        "list_teams_seeding",
                        "list_pools",
                        "list_swiss_rounds",
                        "list_brackets",
                        "list_cross_pools",
                        "list_position_pools",
                        "list_fields",
                        "list_matches",
                        "get_standings",
                        "get_schedule_grid",
                    }
                    action_tools = {
                        "ask_user",
                        "propose_recommended_schedule",
                        "propose_create_pool",
                        "propose_full_setup",
                        "propose_bulk_schedule",
                    }
                    if (
                        round_i < 2
                        and called_names
                        and all(n in read_only for n in called_names)
                        and not any(n in action_tools for n in called_names)
                    ):
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "You have enough context from read tools. "
                                    "Now take action: if the staff request is ambiguous about "
                                    "format (pools vs Swiss), call ask_user; if they asked for a "
                                    "schedule, call propose_recommended_schedule with start_date "
                                    "and duration_mins."
                                ),
                            }
                        )
                    continue

                final_text = result.content or ""
                # If model refused tools on first round, nudge once (keep tool_choice=auto).
                if round_i == 0 and not result.tool_calls:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You must use a tool now. "
                                "If the request is ambiguous about format, call ask_user. "
                                "If the request is about scheduling, call propose_recommended_schedule. "
                                "Do not answer in plain text without tools."
                            ),
                        }
                    )
                    continue
                break
        except OpenCodeGoError as exc:
            final_text = f"Agent error: {exc}"
            self.last_trace.append({"error": str(exc)})

        if assistant_msg is None:
            assistant_msg = TournamentAgentMessage.objects.create(
                session=session,
                role=MessageRole.ASSISTANT,
                content=final_text,
                message_kind=MessageKind.TEXT,
                model_id=session.model_id,
            )
        else:
            if final_text:
                assistant_msg.content = final_text
                assistant_msg.save(update_fields=["content"])

        persist_tool_events()

        yield {
            "type": "done",
            "payload": {
                "response": assistant_msg.content,
                "pending_question": None,
                "pending_proposals": self._pending_proposals(session),
                "session_id": session.id,
                "model_id": session.model_id,
                "message_id": assistant_msg.id,
                "tool_events": turn_tool_events,
                "trace": self.last_trace,
            },
        }

    # NOTE: the *_events methods deliberately are not generator functions. Persisting
    # the message and validating the answer must happen when the method is called, not
    # deferred to the first next() once the response body is already streaming.

    def process_message_events(
        self, session: TournamentAgentSession, message: str
    ) -> Iterator[dict[str, Any]]:
        """Streaming twin of `process_message`."""
        display = message
        masked = scrub_user_text(message)
        TournamentAgentMessage.objects.create(
            session=session,
            role=MessageRole.USER,
            content=display,
            message_kind=MessageKind.TEXT,
            payload={"masked_content": masked},
        )
        return self._run_agent_events(session, user_content_for_model=masked)

    def answer_question_events(
        self,
        session: TournamentAgentSession,
        question_id: int,
        selected_ids: list[str],
        other_text: str | None = None,
        skip: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Streaming twin of `answer_question`. Raises ValueError on a bad answer."""
        model_text = self._record_answer(
            session, question_id, selected_ids, other_text=other_text, skip=skip
        )
        return self._run_agent_events(session, user_content_for_model=model_text)

    def _serialize_proposal(self, row: AgentProposal) -> dict[str, Any]:
        return {
            "id": row.id,
            "tool_name": row.tool_name,
            "summary": row.summary,
            "payload": row.payload,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }

    def _serialize_proposal_by_id(
        self, session: TournamentAgentSession, proposal_id: int
    ) -> dict[str, Any] | None:
        row = session.proposals.filter(id=proposal_id).first()
        return self._serialize_proposal(row) if row else None

    def _pending_proposals(self, session: TournamentAgentSession) -> list[dict[str, Any]]:
        return [
            self._serialize_proposal(row)
            for row in session.proposals.filter(status="pending").order_by("-created_at")
        ]

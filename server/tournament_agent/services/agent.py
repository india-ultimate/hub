"""Tournament agent service: tool loop with PII masking and propose/confirm."""

from __future__ import annotations

import json
import time
from collections.abc import Generator, Iterator
from typing import Any

from django.conf import settings
from django.utils import timezone

from server.core.models import User
from server.tournament.models import Tournament
from server.tournament_agent.catalog import default_model_id, is_allowed_model
from server.tournament_agent.clients.opencode import (
    ChatCompletionResult,
    OpenCodeGoClient,
    OpenCodeGoError,
)
from server.tournament_agent.models import (
    AgentProposal,
    AgentQuestion,
    MessageKind,
    MessageRole,
    ProposalStatus,
    QuestionSelectionMode,
    QuestionStatus,
    TournamentAgentMessage,
    TournamentAgentSession,
)
from server.tournament_agent.privacy.display import (
    TokenTextStream,
    player_names_for_payload,
    resolve_player_tokens,
)
from server.tournament_agent.privacy.mask import scrub_user_text
from server.tournament_agent.services.skills import load_skills, render_skills, select_skills
from server.tournament_agent.tools import (
    READ_ONLY_TOOLS,
    TOOL_DEFINITIONS,
    AskUserPause,
    ToolContext,
    dispatch_tool,
)

BASE_PROMPT = """You are the Tournament Manager AI Agent for India Ultimate Hub.
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

"""


def build_system_prompt(tournament: Tournament, user_text: str = "") -> str:
    """Base rules plus the skills relevant to this tournament and this turn."""
    skills = select_skills(load_skills(), tournament_status=tournament.status, user_text=user_text)
    return BASE_PROMPT + render_skills(skills)


MAX_EVENT_ARGS_CHARS = 4000
# The context-gathering nudge is a stall-breaker, not a policy: after this many
# rounds the model is left to finish the turn however it sees fit.
MAX_NUDGE_ROUNDS = 2

# Model-facing history only. The UI still shows every stored message; this is
# what we replay into the next chat() call so the window and quota stay bounded.
KEEP_RECENT_MESSAGES = 12
HISTORY_CHAR_BUDGET = 20_000
COMPACT_TURN_CHARS = 280
COMPACT_DIGEST_CHARS = 8_000


def _truncate_chars(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"


def _compact_model_turns(turns: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Fold older turns into a digest. Returns (digest_or_empty, recent_turns).

    Live scores and roster state must still come from tools — the digest is a
    recap of what staff asked, not a source of truth.
    """
    if not turns:
        return "", []

    total = sum(len(t.get("content") or "") for t in turns)
    if len(turns) <= KEEP_RECENT_MESSAGES and total <= HISTORY_CHAR_BUDGET:
        return "", turns

    keep_n = min(KEEP_RECENT_MESSAGES, len(turns))
    older, recent = turns[:-keep_n], turns[-keep_n:]
    digest = ""
    if older:
        lines: list[str] = []
        for turn in older:
            speaker = "Staff" if turn.get("role") == "user" else "Agent"
            snippet = _truncate_chars(str(turn.get("content") or ""), COMPACT_TURN_CHARS)
            lines.append(f"{speaker}: {snippet}")
        digest = (
            f"Earlier in this session ({len(older)} messages compacted). "
            "Tournament state may have changed — use tools, not this recap, "
            "for live scores, seeding, or who is in which stage.\n"
            + "\n".join(lines)
        )
        digest = _truncate_chars(digest, COMPACT_DIGEST_CHARS)

    recent_total = sum(len(t.get("content") or "") for t in recent)
    while len(recent) > 2 and (len(digest) + recent_total) > HISTORY_CHAR_BUDGET:
        dropped = recent.pop(0)
        recent_total -= len(dropped.get("content") or "")
    return digest, recent


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
        # Confirmed/rejected proposals stay for audit, but pending ones belong to a
        # conversation that no longer exists — leaving them would keep offering
        # staff a Confirm button for a plan they can no longer read.
        session.proposals.filter(status=ProposalStatus.PENDING).update(
            status=ProposalStatus.EXPIRED, resolved_at=timezone.now()
        )
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
        # One pass over the whole response: assistant text and the tool events stored
        # on each message can all carry `{{player:<id>}}`.
        return resolve_player_tokens(
            {
                "session_id": session.id,
                "tournament_id": session.tournament_id,
                "model_id": session.model_id,
                "messages": messages,
                "pending_question": self._serialize_question(pending_q) if pending_q else None,
                "pending_proposals": self._pending_proposals(session),
            },
            session.tournament,
        )

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

    def process_message(self, session: TournamentAgentSession, message: str) -> dict[str, Any]:
        display = message
        masked = scrub_user_text(message)
        TournamentAgentMessage.objects.create(
            session=session,
            role=MessageRole.USER,
            content=display,
            message_kind=MessageKind.TEXT,
            payload={"masked_content": masked},
        )
        return self._run_agent(session)

    def answer_question(
        self,
        session: TournamentAgentSession,
        question_id: int,
        selected_ids: list[str],
        other_text: str | None = None,
        skip: bool = False,
    ) -> dict[str, Any]:
        self._record_answer(session, question_id, selected_ids, other_text=other_text, skip=skip)
        return self._run_agent(session)

    def _record_answer(
        self,
        session: TournamentAgentSession,
        question_id: int,
        selected_ids: list[str],
        other_text: str | None = None,
        skip: bool = False,
    ) -> None:
        """Validate and persist a question answer.

        The model reads the answer back off the stored message like any other user
        turn, so nothing needs to be handed to the caller.
        """
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
            TournamentAgentMessage.objects.create(
                session=session,
                role=MessageRole.USER,
                content="User cancelled the clarifying question.",
                message_kind=MessageKind.ANSWER,
                payload={"question_id": question.id, "skipped": True, "cancelled": True},
            )
            return

        selected_ids = [str(x) for x in selected_ids]
        option_ids = {str(o["id"]) for o in question.options}
        if any(sid not in option_ids for sid in selected_ids):
            raise ValueError("Invalid option id")
        if (
            question.selection_mode == QuestionSelectionMode.SINGLE
            and len(selected_ids) != 1
            and not (question.allow_other and other_text and not selected_ids)
        ):
            raise ValueError("Single select requires exactly one option")
        if (
            question.selection_mode == QuestionSelectionMode.MULTI
            and not selected_ids
            and not (question.allow_other and other_text)
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

    def _build_model_messages(self, session: TournamentAgentSession) -> list[dict[str, Any]]:
        turns: list[dict[str, Any]] = []
        for m in session.messages.all():
            if m.role == MessageRole.USER:
                content = (m.payload or {}).get("masked_content") or scrub_user_text(m.content)
                turns.append({"role": "user", "content": content})
            elif m.role == MessageRole.ASSISTANT:
                turns.append({"role": "assistant", "content": m.content or ""})

        latest_user = next((t["content"] for t in reversed(turns) if t["role"] == "user"), "")
        digest, recent = _compact_model_turns(turns)
        system = build_system_prompt(session.tournament, latest_user)
        if digest:
            system = f"{system}\n\n## Earlier conversation (compacted)\n{digest}"
        return [{"role": "system", "content": system}, *recent]

    def _chat_round(
        self,
        session: TournamentAgentSession,
        messages: list[dict[str, Any]],
    ) -> Generator[dict[str, Any], None, ChatCompletionResult]:
        """One model call. Yields text_delta events; returns the assembled result."""
        if not self.streaming:
            return self.client.chat(
                model_id=session.model_id,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

        streamed: list[str] = []
        result: ChatCompletionResult | None = None
        # Names are substituted as the text goes past, so a `{{player:812}}` never
        # flashes up raw. The stream holds back anything that could still become a
        # token, since one can arrive split across two chunks.
        text_stream = TokenTextStream(session.tournament)
        for chunk in self.client.chat_stream(
            model_id=session.model_id,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        ):
            if chunk.type == "text" and chunk.text:
                streamed.append(chunk.text)
                ready = text_stream.feed(chunk.text)
                if ready:
                    yield {"type": "text_delta", "text": ready}
            elif chunk.type == "result":
                result = chunk.result
        tail = text_stream.flush()
        if tail:
            yield {"type": "text_delta", "text": tail}
        if result is None:
            raise OpenCodeGoError("Stream ended without a result")
        # Models that emit tool calls as text get that text stripped from the reply.
        # The raw blob was already streamed, so correct what the client is showing.
        # But don't blank the display: if the provider stripped content to empty while
        # the user already saw text, keep the streamed version visible during tool
        # rounds — otherwise the UI flashes the first word then goes blank.
        raw_streamed = "".join(streamed)
        final_content = result.content or ""
        if raw_streamed and final_content != raw_streamed and final_content:
            yield {
                "type": "text_replace",
                "text": resolve_player_tokens(final_content, session.tournament),
            }
        return result

    def _resolved_events(
        self, events: Iterator[dict[str, Any]], session: TournamentAgentSession
    ) -> Iterator[dict[str, Any]]:
        """Every event on its way to the browser gets its player tokens resolved.

        `text_delta` is already resolved by `_chat_round`, so this is a no-op pass
        for it; what it catches is the reply text on `done`, ask_user prompts and
        option labels, proposal summaries, and the tool-event arguments.
        """
        for event in events:
            yield resolve_player_tokens(event, session.tournament)

    def _run_agent(self, session: TournamentAgentSession) -> dict[str, Any]:
        """Drain the event stream and return only the final payload."""
        payload: dict[str, Any] = {}
        for event in self._resolved_events(self._run_agent_events(session), session):
            if event["type"] == "done":
                payload = event["payload"]
        return payload

    def _run_agent_events(self, session: TournamentAgentSession) -> Iterator[dict[str, Any]]:
        messages = self._build_model_messages(session)

        self.last_trace = []
        pending_question = None
        final_text = ""
        assistant_msg: TournamentAgentMessage | None = None
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
                result = yield from self._chat_round(session, messages)
                self.last_trace.append(
                    {
                        "round": round_i,
                        "finish_reason": result.finish_reason,
                        "content_preview": (result.content or "")[:300],
                        "tool_calls": [
                            {"name": tc.get("name"), "id": tc.get("id")} for tc in result.tool_calls
                        ],
                    }
                )

                if result.tool_calls:
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
                        except Exception as exc:  # — model must see and recover from tool errors
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

                    # If the model only gathered context, push it to finish the turn once.
                    # Deliberately does not demand a mutation: plenty of turns are staff
                    # asking a question, and telling the model to propose something
                    # anyway is how an "what do the standings look like?" turn ends in an
                    # unwanted ask_user or proposal.
                    only_read = called_names and all(n in READ_ONLY_TOOLS for n in called_names)
                    if round_i < MAX_NUDGE_ROUNDS and only_read:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "You have read enough. Finish the turn now: if the staff "
                                    "member asked a question, answer it in plain text; if they "
                                    "asked for a change, call ask_user when the request is "
                                    "ambiguous about format, days or fields, or the matching "
                                    "propose_* tool when it is not."
                                ),
                            }
                        )
                    continue

                final_text = result.content or ""
                # If the model refused tools on the first round, nudge it once.
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
        elif final_text:
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
        return self._resolved_events(self._run_agent_events(session), session)

    def answer_question_events(
        self,
        session: TournamentAgentSession,
        question_id: int,
        selected_ids: list[str],
        other_text: str | None = None,
        skip: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Streaming twin of `answer_question`. Raises ValueError on a bad answer."""
        self._record_answer(session, question_id, selected_ids, other_text=other_text, skip=skip)
        return self._resolved_events(self._run_agent_events(session), session)

    def _serialize_proposal(self, row: AgentProposal) -> dict[str, Any]:
        tournament = row.session.tournament
        return {
            "id": row.id,
            "tool_name": row.tool_name,
            "summary": resolve_player_tokens(row.summary, tournament),
            "payload": row.payload,
            # The payload keeps bare ids — it is replayed into the applier verbatim —
            # so names for the ids it mentions travel alongside it instead.
            "player_names": player_names_for_payload(row.payload, tournament),
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }

    def _serialize_proposal_by_id(
        self, session: TournamentAgentSession, proposal_id: int
    ) -> dict[str, Any] | None:
        row = (
            session.proposals.select_related("session__tournament__event")
            .filter(id=proposal_id)
            .first()
        )
        return self._serialize_proposal(row) if row else None

    def _pending_proposals(self, session: TournamentAgentSession) -> list[dict[str, Any]]:
        return [
            self._serialize_proposal(row)
            for row in session.proposals.select_related("session__tournament__event")
            .filter(status=ProposalStatus.PENDING)
            .order_by("created_at")
        ]

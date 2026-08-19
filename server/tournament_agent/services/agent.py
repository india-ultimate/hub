"""Tournament agent service: tool loop with PII masking and propose/confirm."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Generator, Iterator
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from server.core.models import User
from server.tournament.models import Tournament
from server.tournament.utils import can_manage_tournament
from server.tournament_agent.catalog import configured_default_model_id, is_allowed_model
from server.tournament_agent.clients.opencode import (
    TOOL_CHOICE_AUTO,
    TOOL_CHOICE_REQUIRED,
    ChatCompletionResult,
    OpenCodeGoClient,
    OpenCodeGoError,
)
from server.tournament_agent.domain.next_step import next_step_for, placeholder_for
from server.tournament_agent.domain.phase import Phase, phase_for, phase_line
from server.tournament_agent.domain.state import (
    TournamentSnapshot,
    build_snapshot,
    render_state,
)
from server.tournament_agent.models import (
    AgentProposal,
    AgentQuestion,
    AgentTurn,
    MessageKind,
    MessageRole,
    ProposalStatus,
    QuestionSelectionMode,
    QuestionStatus,
    TournamentAgentMessage,
    TournamentAgentSession,
    TurnOutcome,
)
from server.tournament_agent.policy import phase_rejection, tool_definitions_for
from server.tournament_agent.privacy.display import (
    TokenTextStream,
    player_names_for_payload,
    resolve_player_tokens,
)
from server.tournament_agent.privacy.mask import scrub_user_text
from server.tournament_agent.services.skills import load_skills, render_skills, select_skills
from server.tournament_agent.tools import (
    READ_ONLY_TOOLS,
    AskUserPause,
    ToolContext,
    dispatch_tool,
)

BASE_PROMPT = """You are the Tournament Manager AI Agent for India Ultimate Hub.
You help staff design pools, Swiss groups, brackets, schedules, and orchestrate tournaments.

The tournament state block below is read from the database at the start of this turn. It is what
is true about this event; your own earlier messages are not. Anything you planned that the block
does not list did not happen, so do not tell staff it exists.

You are only offered the tools that are legal in the current phase, and the phase line says what
comes next. You never write to the tournament yourself: a propose_* tool records a plan and staff
Confirm it on the card. Confirm and Reject are buttons, never chat replies.

Rules:
- Never invent personal data. You only see allowlisted ops fields (teams, seeds, matches, fields, times).
- Ask with ask_user BEFORE any propose_* when the shape of the event is unspecified: how many fields when none exist, or pools vs Swiss for the initial stage. Staff handing you the choice is not the same as having made it — "configure it however you think is best", "whichever you prefer" and "I'm open either way" are all still asks, because the format decides every match that follows. Ask once, then wait for the answer; never propose a format and ask about it in the same turn.
- A request that names its own dates, durations, counts or fields is NOT ambiguous. Act on it. Do not ask staff to re-confirm a date they just gave you, and do not stop because that date sits outside the event window — schedule what they asked for.
- When staff name a match loosely ("the first pool game"), read the matches and pick the obvious one. Unscheduled matches still have an order: their sequence number.
- A bracket named "1-4" already includes every placement game: 1v4 and 2v3, the final, and the 3v4 push-in. Never add a separate 3-4 bracket for it.
- If a pending proposal shows an apply error, call the matching propose_* tool with a corrected payload. Do not reuse the failed one, and do not ask staff to Reject it first.
- Be concise. Use markdown in final replies only after tools have been used.

Examples:
- User: "Set up this tournament for me"
  → The phase says which step is missing. If the format is unspecified, ask_user pools vs Swiss before proposing either. Do that one step and stop.
- User: "Recommend a schedule for Saturday starting 2026-08-01 with 75 minute games"
  → Everything needed is in the request. Read fields and matches, then one propose_recommended_schedule with that date and duration, then check_schedule_conflicts. Do not ask.
- User: "Confirming proposal #47 failed: two matches on the same field at the same time"
  → The state block carries the apply error. Propose a corrected schedule that does not double-book a slot.
"""


def build_system_prompt(tournament: Tournament, user_text: str = "", phase: str = "") -> str:
    """Base rules plus the skills relevant to this tournament, phase and turn."""
    skills = select_skills(
        load_skills(),
        tournament_status=tournament.status,
        user_text=user_text,
        phase=phase,
    )
    return BASE_PROMPT + render_skills(skills)


BUDGET_MESSAGE = (
    "This conversation has used its token budget. Clear the history to start a "
    "fresh session — the tournament itself is untouched."
)
DAILY_BUDGET_MESSAGE = (
    "You have used today's agent token budget. It resets tomorrow; ask a staff "
    "member if you need it raised."
)


def round_tokens(result: ChatCompletionResult) -> tuple[int, int]:
    """Usage for one round, tolerant of a provider that reports none.

    Not every gateway fills in `usage`, and a missing token count must never be
    the thing that ends a staff member's turn — it just means this round does not
    count towards the budget.
    """
    try:
        raw_in, raw_out = result.tokens
        return max(int(raw_in), 0), max(int(raw_out), 0)
    except (AttributeError, TypeError, ValueError):
        return 0, 0


def budget_refusal(session: TournamentAgentSession) -> str:
    """Why this turn must not start, or empty when it may.

    Rounds are already capped, but nothing capped a long conversation or a long
    day — and an agent that quietly burns a month of quota during one tournament
    is its own kind of outage.
    """
    if not settings.TOURNAMENT_AGENT_ENABLED:
        return "The tournament agent is currently switched off."

    spent = AgentTurn.objects.filter(session=session).aggregate(
        total=Sum("tokens_in") + Sum("tokens_out")
    )["total"]
    if (spent or 0) >= settings.TOURNAMENT_AGENT_MAX_SESSION_TOKENS:
        return BUDGET_MESSAGE

    since = timezone.now() - timedelta(days=1)
    daily = AgentTurn.objects.filter(
        session__user_id=session.user_id, created_at__gte=since
    ).aggregate(total=Sum("tokens_in") + Sum("tokens_out"))["total"]
    if (daily or 0) >= settings.TOURNAMENT_AGENT_MAX_DAILY_TOKENS:
        return DAILY_BUDGET_MESSAGE
    return ""


MAX_EVENT_ARGS_CHARS = 4000
# The context-gathering nudge is a stall-breaker, not a policy: after this many
# rounds the model is left to finish the turn however it sees fit.
MAX_NUDGE_ROUNDS = 2

# Model-facing history only. The UI still shows every stored message; this is
# what we replay into the next chat() call so the window and quota stay bounded.
KEEP_RECENT_MESSAGES = 12
MIN_RECENT_MESSAGES = 2
HISTORY_CHAR_BUDGET = 20_000
COMPACT_TURN_CHARS = 280
COMPACT_DIGEST_CHARS = 8_000
SKIP_FOLLOWUP = "Skipped. What would you like to do next?"


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
            "for live scores, seeding, or who is in which stage.\n" + "\n".join(lines)
        )
        digest = _truncate_chars(digest, COMPACT_DIGEST_CHARS)

    recent_total = sum(len(t.get("content") or "") for t in recent)
    while len(recent) > MIN_RECENT_MESSAGES and (len(digest) + recent_total) > HISTORY_CHAR_BUDGET:
        dropped = recent.pop(0)
        recent_total -= len(dropped.get("content") or "")
    return digest, recent


# How many of a turn's tool calls are replayed back to the model next turn. A long
# setup turn's tail is the part that matters — the proposals it ended on.
MAX_REPLAYED_EVENTS = 8
EVENT_SUMMARY_CHARS = 90


def _with_tool_evidence(content: str, payload: dict[str, Any] | None) -> str:
    """An assistant turn plus a one-line record of what its tools actually returned."""
    events = (payload or {}).get("tool_events") or []
    if not events:
        return content
    parts = []
    for event in events[-MAX_REPLAYED_EVENTS:]:
        name = event.get("name") or "?"
        summary = _truncate_chars(str(event.get("summary") or ""), EVENT_SUMMARY_CHARS)
        status = event.get("status")
        label = name if status in ("ok", "proposal") else f"{name}[{status}]"
        parts.append(f"{label} → {summary}" if summary else label)
    trace = "[tools this turn: " + "; ".join(parts) + "]"
    return f"{content}\n{trace}" if content else trace


# Deliberately anchored on the word: a bare `#4` is far more often a seed, a pool
# label or a table cell than a proposal, and rewriting those mangles good replies.
_PROPOSAL_REF_RE = re.compile(r"\bproposals?\s*#?\s*(\d+)", re.IGNORECASE)
PHANTOM_PROPOSAL_TEXT = "the proposal above"


def strip_phantom_proposal_ids(text: str, real_ids: set[int]) -> str:
    """Rewrite proposal ids the turn cannot account for.

    The state block and the phase gate remove most of the reasons a model invents
    "Proposal #47 is ready to confirm", but staff hunting for a card that does not
    exist is bad enough to be worth one last check. An id that was created this
    turn, is pending, or was applied in this session is real and is left alone;
    anything else loses its number rather than its sentence.
    """
    if not text:
        return text

    def replace(match: re.Match[str]) -> str:
        return match.group(0) if int(match.group(1)) in real_ids else PHANTOM_PROPOSAL_TEXT

    return _PROPOSAL_REF_RE.sub(replace, text)


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
        # The phase the most recent turn ran in — read by the evals and by tests.
        self.last_phase: Phase | None = None
        # When on, model text is pulled via chat_stream and re-emitted as text_delta
        # events. Off (the default) keeps the single-shot chat() call, so callers and
        # tests that never opted into streaming behave exactly as before.
        self.streaming = streaming

    def get_or_create_session(
        self, tournament_id: int, model_id: str | None = None
    ) -> TournamentAgentSession:
        tournament = Tournament.objects.get(id=tournament_id)
        if not can_manage_tournament(self.user, tournament):
            raise PermissionError("Staff or assigned tournament director only")
        mid = model_id or configured_default_model_id()
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
        questions_by_id = {q.id: q for q in session.questions.all()}
        messages = []
        # Confirm/Reject outcomes are recorded for the model, not for staff — the
        # proposal card already shows staff what they decided, and replaying it as a
        # chat bubble would say the same thing twice.
        for m in session.messages.exclude(role=MessageRole.SYSTEM):
            payload = dict(m.payload or {})
            qid = payload.get("question_id")
            if m.message_kind == MessageKind.QUESTION and qid is not None:
                question = questions_by_id.get(int(qid))
                if question:
                    payload["question_snapshot"] = self._serialize_question(question)
            item: dict[str, Any] = {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "message_kind": m.message_kind,
                "payload": payload,
                "model_id": m.model_id,
                "created_at": m.created_at.isoformat(),
            }
            messages.append(item)
        pending_q = (
            session.questions.filter(status=QuestionStatus.PENDING).order_by("-created_at").first()
        )
        composer_step, composer_placeholder = self._composer(session, pending_q is not None)
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
                "next_step": composer_step,
                "placeholder": composer_placeholder,
            },
            session.tournament,
        )

    def _composer(
        self, session: TournamentAgentSession, question_pending: bool = False
    ) -> tuple[dict[str, str] | None, str]:
        """(next_step, placeholder) for the chat box, both from the current phase.

        The same derivation the tool gate uses, so the UI can never invite staff to
        ask for something the agent would decline.
        """
        snapshot = build_snapshot(session)
        phase = phase_for(snapshot)
        placeholder = placeholder_for(phase)
        if question_pending:
            return None, placeholder
        step = next_step_for(snapshot, phase)
        payload = {"label": step.label, "prompt": step.prompt, "why": step.why} if step else None
        return payload, placeholder

    def _next_step(
        self, session: TournamentAgentSession, question_pending: bool = False
    ) -> dict[str, str] | None:
        return self._composer(session, question_pending)[0]

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
        if skip:
            return self._skip_followup(session)
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
            # Do not start another model turn — that is what re-asks the same
            # options. A short assistant follow-up hands the conversation back.
            question.status = QuestionStatus.SKIPPED
            question.answer = {"skipped": True, "cancelled": True}
            question.answered_at = timezone.now()
            question.save()
            TournamentAgentMessage.objects.create(
                session=session,
                role=MessageRole.USER,
                content=(
                    "Skipped this question. Do not ask it again with the same "
                    "options. Wait for a new instruction."
                ),
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
            and not (other_text and not selected_ids)
        ):
            raise ValueError("Single select requires exactly one option")
        if (
            question.selection_mode == QuestionSelectionMode.MULTI
            and not selected_ids
            and not other_text
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

    def _build_model_messages(
        self,
        session: TournamentAgentSession,
        snapshot: TournamentSnapshot,
        phase: Phase,
    ) -> list[dict[str, Any]]:
        turns: list[dict[str, Any]] = []
        for m in session.messages.all():
            if m.role == MessageRole.USER:
                content = (m.payload or {}).get("masked_content") or scrub_user_text(m.content)
                turns.append({"role": "user", "content": content})
            elif m.role == MessageRole.ASSISTANT:
                # Replay what the turn actually did, not only what it said about it.
                # Without this the model's own "I've created pools A and B" comes back
                # as the most recent authority on a tournament it never changed.
                turns.append(
                    {
                        "role": "assistant",
                        "content": _with_tool_evidence(m.content or "", m.payload),
                    }
                )
            elif m.role == MessageRole.SYSTEM:
                # Confirm/Reject outcomes. Delivered as a user turn because the
                # providers behind the gateway do not all accept a system message
                # part-way through a conversation.
                turns.append({"role": "user", "content": m.content or ""})

        latest_user = next((t["content"] for t in reversed(turns) if t["role"] == "user"), "")
        digest, recent = _compact_model_turns(turns)

        # Ordered stable-first so the prefix stays cacheable: base rules and skills
        # change rarely, the state block changes every round.
        system = build_system_prompt(session.tournament, latest_user, phase.value)
        if digest:
            system = f"{system}\n\n## Earlier conversation (compacted)\n{digest}"
        system = f"{system}\n\n{render_state(snapshot, phase_line(phase))}"
        return [{"role": "system", "content": system}, *recent]

    def _chat_round(
        self,
        session: TournamentAgentSession,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = TOOL_CHOICE_AUTO,
    ) -> Generator[dict[str, Any], None, ChatCompletionResult]:
        """One model call. Yields text_delta events; returns the assembled result."""
        if not self.streaming:
            return self.client.chat(
                model_id=session.model_id,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
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
            tools=tools,
            tool_choice=tool_choice,
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
        # One read of the tournament for the whole turn: the state block, the phase
        # gate and the dispatch guard all answer from this rather than re-querying.
        refusal = budget_refusal(session)
        if refusal:
            yield from self._closed_turn(session, refusal)
            return

        snapshot = build_snapshot(session)
        phase = phase_for(snapshot)
        tools = tool_definitions_for(phase)
        messages = self._build_model_messages(session, snapshot, phase)

        self.last_trace = []
        self.last_phase = phase

        started_turn_at = time.monotonic()
        tokens_in = tokens_out = 0
        rounds_used = 0

        def record_turn(outcome: str, error: str = "") -> None:
            AgentTurn.objects.create(
                session=session,
                phase=phase.value,
                model_id=session.model_id,
                rounds=rounds_used,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=int((time.monotonic() - started_turn_at) * 1000),
                tool_names=[e["name"] for e in turn_tool_events],
                proposal_ids=[
                    int(e["proposal_id"]) for e in turn_tool_events if e.get("proposal_id")
                ],
                outcome=outcome,
                error=error[:2000],
            )

        pending_question = None
        final_text = ""
        turn_error = ""
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
                # Round 0 must produce a tool call: every staff request needs current
                # state, and prose on the first round is the "I've created the pools"
                # failure with nothing behind it. Later rounds go back to "auto" so the
                # model can actually finish the turn. Downgraded automatically for any
                # model the gateway refuses a forced choice for.
                choice = TOOL_CHOICE_REQUIRED if round_i == 0 else TOOL_CHOICE_AUTO
                result = yield from self._chat_round(session, messages, tools, choice)
                rounds_used = round_i + 1
                round_in, round_out = round_tokens(result)
                tokens_in += round_in
                tokens_out += round_out
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
                        # The schema list already excludes tools this phase cannot use,
                        # but a model can call one it saw two rounds ago, or invent a
                        # name. Refuse here too, and say what it may do instead.
                        rejection = phase_rejection(phase, name)
                        if rejection is not None:
                            event["status"] = "error"
                            event["summary"] = rejection["message"][:200]
                            event["duration_ms"] = 0
                            turn_tool_events.append(event)
                            persist_tool_events()
                            self.last_trace.append({"tool": name, "blocked_by_phase": phase.value})
                            yield {"type": "tool_end", "index": event_index, **event}
                            messages.append(
                                {
                                    "role": "tool",
                                    "name": name,
                                    "tool_call_id": tc["id"],
                                    "content": json.dumps(rejection),
                                }
                            )
                            continue
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
                                "question_snapshot": self._serialize_question(pause.question),
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
                            record_turn(TurnOutcome.ASKED)
                            yield {"type": "question", "question": question_payload}
                            yield {
                                "type": "done",
                                "payload": {
                                    "response": assistant_msg.content,
                                    "pending_question": question_payload,
                                    "pending_proposals": self._pending_proposals(session),
                                    "next_step": None,
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
                    #
                    # The ack ("done", "confirmed") and status ("anything else?") nudges
                    # that used to sit here are gone: the state block now says what has
                    # been applied and what is still pending, every round, so there is
                    # nothing left for a regex on the user's phrasing to catch.
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
                # A turn that never calls a tool cannot create a proposal. Models
                # sometimes narrate "Proposal #N is live" in plain text; staff then
                # have nothing to Confirm. Keep nudging past the first refusal.
                if not turn_tool_events and round_i < MAX_NUDGE_ROUNDS:
                    if result.content:
                        messages.append({"role": "assistant", "content": result.content})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You must use a tool now. Plain text does not create a "
                                "proposal, and staff will not see a Confirm button. "
                                "If there are no fields, ask how many then call "
                                "propose_create_field and stop — do not also propose "
                                "stages or a schedule. "
                                "If the request is ambiguous about format, call ask_user. "
                                "If they asked to add, change, or delete something, call "
                                "the matching propose_* tool. "
                                "If the request is about scheduling and fields and stages "
                                "already exist, call propose_recommended_schedule once — "
                                "never stack overlapping grids. "
                                "If they said a Confirm failed, call list_proposals "
                                "then the matching propose_* tool with a corrected "
                                "payload — do not reuse the failed one. "
                                "Never announce a proposal id unless a propose_* tool "
                                "just returned it."
                            ),
                        }
                    )
                    continue
                break
        except OpenCodeGoError as exc:
            final_text = f"Agent error: {exc}"
            turn_error = str(exc)
            self.last_trace.append({"error": str(exc)})

        closing = build_snapshot(session)
        final_text = strip_phantom_proposal_ids(
            final_text,
            {int(e["proposal_id"]) for e in turn_tool_events if e.get("proposal_id")}
            | {row.id for row in closing.pending}
            # Confirmed proposals are real too — staff just cannot click them any
            # more. Leaving them out rewrote "pool A (#61)" on a turn that had
            # correctly reported an applied stage.
            | {row.id for row in closing.applied},
        )

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
        record_turn(
            TurnOutcome.ERROR if turn_error else TurnOutcome.REPLIED,
            turn_error,
        )

        yield {
            "type": "done",
            "payload": {
                "response": assistant_msg.content,
                "pending_question": None,
                "pending_proposals": self._pending_proposals(session),
                "next_step": self._next_step(session),
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
        if skip:
            payload = self._skip_followup(session)

            def skipped() -> Iterator[dict[str, Any]]:
                yield {"type": "text_delta", "text": payload["response"]}
                yield {"type": "done", "payload": payload}

            return skipped()
        return self._resolved_events(self._run_agent_events(session), session)

    def _closed_turn(self, session: TournamentAgentSession, text: str) -> Iterator[dict[str, Any]]:
        """End a turn without calling the model at all — budget spent, agent off.

        Recorded as an assistant message so staff see the reason in the thread
        rather than an empty reply, and so the next turn's history explains the gap.
        """
        assistant_msg = TournamentAgentMessage.objects.create(
            session=session,
            role=MessageRole.ASSISTANT,
            content=text,
            message_kind=MessageKind.TEXT,
            model_id=session.model_id,
        )
        yield {"type": "text_delta", "text": text}
        yield {
            "type": "done",
            "payload": {
                "response": text,
                "pending_question": None,
                "pending_proposals": self._pending_proposals(session),
                "next_step": self._next_step(session),
                "session_id": session.id,
                "model_id": session.model_id,
                "message_id": assistant_msg.id,
                "tool_events": [],
                "trace": [],
            },
        }

    def _skip_followup(self, session: TournamentAgentSession) -> dict[str, Any]:
        """Close a skip without another model call, so the same question cannot loop."""
        assistant_msg = TournamentAgentMessage.objects.create(
            session=session,
            role=MessageRole.ASSISTANT,
            content=SKIP_FOLLOWUP,
            message_kind=MessageKind.TEXT,
            model_id=session.model_id,
        )
        return {
            "response": SKIP_FOLLOWUP,
            "pending_question": None,
            "pending_proposals": self._pending_proposals(session),
            "session_id": session.id,
            "model_id": session.model_id,
            "message_id": assistant_msg.id,
            "tool_events": [],
            "trace": [],
        }

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
            "last_error": row.last_error or "",
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

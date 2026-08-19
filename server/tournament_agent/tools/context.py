"""What every tool is handed, and the guard every result passes through."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.utils import timezone

from server.tournament.models import Tournament
from server.tournament_agent.models import (
    AgentProposal,
    ProposalStatus,
    TournamentAgentMessage,
    TournamentAgentSession,
)
from server.tournament_agent.privacy.mask import assert_safe_tool_payload, scrub_json_strings

ToolHandler = Callable[..., Any]

# One Confirm card for a given match's slot. Four pools in one turn are fine;
# three overlapping grids for the same games are not — only the latest stays.
_SCHEDULE_PLAN_TOOLS = frozenset(
    {
        "propose_recommended_schedule",
        "propose_bulk_schedule",
        "propose_shift_schedule",
    }
)


def _assignment_match_ids(payload: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for row in payload.get("assignments") or []:
        if isinstance(row, dict) and row.get("match_id") is not None:
            ids.add(int(row["match_id"]))
    return ids


_EMPTY_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def _team_map(tournament: Tournament) -> dict[int, str]:
    return {t.id: t.name for t in tournament.teams.only("id", "name")}


def _safe(result: Any) -> Any:
    scrubbed = scrub_json_strings(result)
    assert_safe_tool_payload(scrubbed)
    return scrubbed


class ToolContext:
    def __init__(
        self,
        session: TournamentAgentSession,
        tournament: Tournament,
        assistant_message: TournamentAgentMessage | None = None,
    ) -> None:
        self.session = session
        self.tournament = tournament
        self.assistant_message = assistant_message

    def create_proposal(
        self, tool_name: str, summary: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        # Re-proposing the same tool replaces the earlier plan: staff asked for a
        # change, so the old version must stop being confirmable. Scoped to earlier
        # turns — one turn legitimately emits several proposals from the same tool
        # (four pools in a 16-team setup), and those all stay pending together.
        stale = AgentProposal.objects.filter(
            session=self.session, tool_name=tool_name, status=ProposalStatus.PENDING
        )
        if self.assistant_message is not None:
            stale = stale.exclude(created_by_message=self.assistant_message)
        # EXPIRED, not REJECTED: nobody turned this plan down, it just stopped being
        # the current one.
        stale.update(status=ProposalStatus.EXPIRED, resolved_at=timezone.now())

        if tool_name in _SCHEDULE_PLAN_TOOLS:
            new_ids = _assignment_match_ids(payload)
            if new_ids:
                overlapping = [
                    row.id
                    for row in AgentProposal.objects.filter(
                        session=self.session,
                        tool_name__in=_SCHEDULE_PLAN_TOOLS,
                        status=ProposalStatus.PENDING,
                    )
                    if _assignment_match_ids(row.payload or {}) & new_ids
                ]
                if overlapping:
                    AgentProposal.objects.filter(id__in=overlapping).update(
                        status=ProposalStatus.EXPIRED, resolved_at=timezone.now()
                    )

        proposal = AgentProposal.objects.create(
            session=self.session,
            tool_name=tool_name,
            summary=summary,
            payload=payload,
            status=ProposalStatus.PENDING,
            created_by_message=self.assistant_message,
        )
        if self.assistant_message is not None:
            message_payload = dict(self.assistant_message.payload or {})
            ids = list(message_payload.get("proposal_ids") or [])
            ids.append(proposal.id)
            message_payload["proposal_ids"] = ids
            self.assistant_message.payload = message_payload
            self.assistant_message.save(update_fields=["payload"])
        return _safe(
            {
                "proposal_id": proposal.id,
                "status": proposal.status,
                "summary": summary,
                "message": "Proposal created. Staff must Confirm in the UI before anything is applied.",
            }
        )

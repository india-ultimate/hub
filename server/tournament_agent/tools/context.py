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

        proposal = AgentProposal.objects.create(
            session=self.session,
            tool_name=tool_name,
            summary=summary,
            payload=payload,
            status=ProposalStatus.PENDING,
            created_by_message=self.assistant_message,
        )
        return _safe(
            {
                "proposal_id": proposal.id,
                "status": proposal.status,
                "summary": summary,
                "message": "Proposal created. Staff must Confirm in the UI before anything is applied.",
            }
        )

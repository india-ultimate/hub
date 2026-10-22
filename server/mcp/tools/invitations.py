from typing import Any

from server.mcp.confirm import confirm_then
from server.mcp.dispatch import call_api, denied
from server.mcp.registry import ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import cap, full_name
from server.series.models import SeriesRosterInvitation
from server.series.utils import invitations_for
from server.utils import today

ANSWERS = ["accept", "decline"]


def _row(ctx: ToolContext, invitation: SeriesRosterInvitation) -> dict[str, Any]:
    player = invitation.to_player
    return {
        "invitation_id": invitation.pk,
        "series_slug": invitation.series.slug,
        "series_name": invitation.series.name,
        "team_slug": invitation.team.slug,
        "team_name": invitation.team.name,
        "player": {
            "player_id": player.pk,
            "full_name": full_name(player.user),
            "is_you": player.user_id == ctx.user.pk,
        },
        "role": invitation.role,
        "invited_by": full_name(invitation.from_user),
        "expires_on": str(invitation.expires_on),
        "expired": invitation.expires_on < today(),
    }


def _pending(ctx: ToolContext) -> Any:
    return (
        invitations_for(ctx.user)
        .filter(status=SeriesRosterInvitation.Status.PENDING)
        .select_related("series", "team", "from_user", "to_player__user")
    )


@tool(
    "list_series_invitations",
    title="List series invitations",
    description=(
        "Pending invitations to join a team's series roster, for you and for the wards you are "
        "guardian of. Each has invitation_id, series_slug, team_slug, the player, role and "
        "expires_on; expired=true ones can no longer be answered. Answer one with "
        "answer_series_invitation."
    ),
    input_schema={"type": "object", "additionalProperties": False},
)
def list_series_invitations(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    rows = [_row(ctx, i) for i in _pending(ctx).order_by("expires_on", "id")]
    return ok(
        cap({"invitations": rows}, list_key="invitations", hint="Ask about one series or team.")
    )


@tool(
    "answer_series_invitation",
    title="Accept or decline a series invitation",
    description=(
        "Accept or decline a series roster invitation by invitation_id, for yourself or a ward "
        "you are guardian of. Accepting puts the player on the team's series roster, if they "
        "are eligible. Hub asks the user to confirm first."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "invitation_id": {"type": "integer"},
            "answer": {"type": "string", "enum": ANSWERS},
        },
        "required": ["invitation_id", "answer"],
        "additionalProperties": False,
    },
    writes=True,
    destructive=True,
)
def answer_series_invitation(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    path = f"/api/series/invitation/{args['invitation_id']}/{args['answer']}"

    def act() -> ToolResult:
        response = call_api(ctx, "PUT", path)
        if not response.ok:
            return denied(response)
        return ok({"done": True, "answer": args["answer"], "invitation_id": args["invitation_id"]})

    invitation = _pending(ctx).filter(pk=args["invitation_id"]).first()
    if invitation is None:
        return fail(f"No pending invitation {args['invitation_id']} for you or your wards")
    who = full_name(invitation.to_player.user)
    verb = "Join" if args["answer"] == "accept" else "Decline joining"
    return confirm_then(
        ctx,
        message=(
            f"{verb} {invitation.team.name} in {invitation.series.name} for {who}? "
            "Answering cannot be changed afterwards."
        ),
        binding=args,
        action=act,
    )

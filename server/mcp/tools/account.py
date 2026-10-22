from typing import Any

from server.committee.routing import committees_of
from server.mcp.dispatch import call_api
from server.mcp.registry import ToolContext, ToolResult, fail, ok, roles_of, tool
from server.tournament.models import Tournament


def _tournaments(rows: Any) -> list[dict[str, str]]:
    return [{"event_slug": t.event.slug, "title": t.event.title} for t in rows]


@tool(
    "whoami",
    title="Who am I",
    description=(
        "The signed-in Hub user: their user_id, name, player_id, the wards they are "
        "guardian of, the teams they administer, committees, tournaments they direct or volunteer at, "
        "whether they can post announcements, and their roles."
    ),
    input_schema={"type": "object", "additionalProperties": False},
)
def whoami(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    response = call_api(ctx, "GET", "/api/me")
    if not response.ok:
        return fail(response.message)
    me = response.data
    player = me.get("player")
    return ok(
        {
            "user_id": me["id"],
            "full_name": me["full_name"],
            "email": me["email"],
            "is_staff": me["is_staff"],
            "player_id": player["id"] if player else None,
            "wards": [{"player_id": w["id"], "full_name": w["full_name"]} for w in me["wards"]],
            "admin_teams": [
                {"team_id": t["id"], "team_slug": t["slug"], "name": t["name"]}
                for t in me["admin_teams"]
            ],
            "committees": [{"name": c.name, "slug": c.slug} for c in committees_of(ctx.user)],
            "directed_tournaments": _tournaments(
                Tournament.objects.filter(directors=ctx.user).select_related("event")
            ),
            "volunteer_tournaments": _tournaments(
                Tournament.objects.filter(volunteers=ctx.user).select_related("event")
            ),
            "can_post_announcements": me["can_post_announcements"],
            "roles": sorted(roles_of(ctx.user)),
            "payment_accounts": [
                {"slug": a["slug"], "name": a["name"]} for a in me["payment_accounts"]
            ],
        }
    )

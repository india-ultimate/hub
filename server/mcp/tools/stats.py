from typing import Any

from server.mcp.dispatch import call_api, denied
from server.mcp.registry import ToolContext, ToolResult, ok, tool
from server.mcp.shape import cap

COVERAGE = (
    "Your own tournament registrations only, not your wards'. Goals, assists and blocks come "
    "from Hub Wrapped, which is built per calendar year after the year ends, so a recent or "
    "future year may not have one."
)
HIDDEN = {"id", "player", "created_at", "updated_at"}


def _registration(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_name": row["event_name"],
        "series_name": row["series_name"],
        "team_id": row["team"]["id"],
        "team_slug": row["team"]["slug"],
        "team_name": row["team"]["name"],
        "role": row["role"],
        "is_playing": row["is_playing"],
        "points": row["points"],
    }


@tool(
    "get_my_stats",
    title="My playing stats",
    description=(
        "Your tournament history (event, team, role, points) and your Hub Wrapped year "
        "stats: tournaments, games, scores, assists, blocks, MVPs, best tournaments, teams "
        "and top teammates. year picks the Wrapped year; the newest one by default. "
        "Read coverage for what is and is not included."
    ),
    input_schema={
        "type": "object",
        "properties": {"year": {"type": "integer", "minimum": 2000, "maximum": 2100}},
        "additionalProperties": False,
    },
)
def get_my_stats(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    registrations = call_api(ctx, "GET", "/api/me/registrations")
    if not registrations.ok:
        return denied(registrations)
    every = call_api(ctx, "GET", "/api/wrapped/")
    years = [w["year"] for w in every.data] if every.ok else []
    year = args.get("year", years[0] if years else None)
    wrapped = None
    note = None
    if year is not None:
        found = next((w for w in every.data if w["year"] == year), None) if every.ok else None
        wrapped = {k: v for k, v in found.items() if k not in HIDDEN} if found else None
    if wrapped is None:
        note = f"No Hub Wrapped for {year}." if year else "No Hub Wrapped yet."
    out = {
        "registrations": [_registration(r) for r in registrations.data],
        "wrapped": wrapped,
        "wrapped_years": years,
        "wrapped_note": note,
        "coverage": COVERAGE,
    }
    return ok(cap(out, list_key="registrations", hint="Ask about one event."))

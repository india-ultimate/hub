import datetime
from typing import Any

from django.utils.timezone import get_current_timezone

from server.mcp.dispatch import ApiResponse, call_api
from server.mcp.registry import ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import SLUG_SCHEMA, cap, full_name, slug_problem
from server.tournament.models import Match, MatchEvent, MatchStats, Tournament

LEADERBOARD_ROWS = 25
SEARCH_LIMIT = 10
SEARCH_YEARS = 5
SEARCH_MIN_LETTERS = 2
VIEWS = ["overview", "schedule", "standings", "spirit", "leaderboard"]


def _team(team: dict[str, Any]) -> dict[str, Any]:
    return {
        "team_id": team["id"],
        "team_slug": team["slug"],
        "name": team["name"],
    }


def _label(choices: Any, value: str) -> str:
    return str(choices(value).label)


def _items(response: ApiResponse) -> list[dict[str, Any]]:
    return list(response.data["items"]) if response.ok else []


def _match(match: dict[str, Any]) -> dict[str, Any]:
    stage = next(
        (match[k] for k in ("pool", "bracket", "position_pool", "swiss_round") if match.get(k)),
        None,
    )
    return {
        "match_id": match["id"],
        "name": match["name"],
        "status": _label(Match.Status, match["status"]),
        "time": match["time"],
        "field": match["field"]["name"] if match["field"] else None,
        "stage": stage["name"] if stage else None,
        "team_1": _team(match["team_1"]) if match["team_1"] else None,
        "team_2": _team(match["team_2"]) if match["team_2"] else None,
        "score_team_1": match["score_team_1"],
        "score_team_2": match["score_team_2"],
    }


@tool(
    "search",
    title="Search Hub",
    description=(
        "Find teams, tournaments, series and players by name. Returns team_id and team_slug, "
        "event_slug, series_slug and player_id to use with other tools. "
        "Player results are names only."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 100},
            "kind": {"type": "string", "enum": ["team", "tournament", "series", "player"]},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def search(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    text = args["query"].strip().casefold()
    if len(text) < SEARCH_MIN_LETTERS:
        return fail("Search needs at least 2 letters")
    kind = args.get("kind")
    out: dict[str, Any] = {}
    if kind in (None, "team"):
        found = _items(call_api(ctx, "GET", "/api/teams/search", query={"text": text}))
        out["teams"] = [_team(t) for t in found[:SEARCH_LIMIT]]
    if kind in (None, "tournament"):
        out["tournaments"] = _find_tournaments(ctx, text)
    if kind in (None, "series"):
        response = call_api(ctx, "GET", "/api/series/all")
        out["series"] = [
            {"series_slug": s["slug"], "name": s["name"]}
            for s in (response.data if response.ok else [])
            if _has_words(text, s["name"], s["slug"])
        ][:SEARCH_LIMIT]
    if kind in (None, "player"):
        found = _items(call_api(ctx, "GET", "/api/players/search", query={"text": text}))
        out["players"] = [
            {"player_id": p["id"], "full_name": p["full_name"]} for p in found[:SEARCH_LIMIT]
        ]
    return ok(out)


def _has_words(text: str, *fields: str | None) -> bool:
    haystack = " ".join(f for f in fields if f).casefold()
    return all(word in haystack for word in text.split())


def _find_tournaments(ctx: ToolContext, text: str) -> list[dict[str, Any]]:
    first = call_api(ctx, "GET", "/api/tournaments/public")
    if not first.ok:
        return []
    found: dict[str, dict[str, Any]] = {}

    def collect(cards: list[dict[str, Any]]) -> None:
        for card in cards:
            event = card["event"]
            if _has_words(text, event["title"], event["slug"]):
                found.setdefault(
                    event["slug"],
                    {
                        "event_slug": event["slug"],
                        "title": event["title"],
                        "start_date": event["start_date"],
                    },
                )

    collect(list(first.data["tournaments"]))
    for year in first.data["years"][:SEARCH_YEARS]:
        if len(found) >= SEARCH_LIMIT:
            break
        collect(_year_cards(ctx, year))
    return list(found.values())[:SEARCH_LIMIT]


def _year_cards(ctx: ToolContext, year: int) -> list[dict[str, Any]]:
    response = call_api(ctx, "GET", "/api/tournaments/public", query={"year": year})
    return list(response.data["tournaments"]) if response.ok else []


@tool(
    "get_tournament",
    title="Get a tournament",
    description=(
        "A tournament's public schedule, standings and teams by event_slug (a director's own reads are read_tournament_ops). view=overview (default): dates, status, location, teams. "
        "schedule: every match with match_id, time, field, teams and score; filter with "
        "team_slug and day (YYYY-MM-DD) to answer when and where a team plays. "
        "standings: pool, bracket and position-pool tables (not cross pools or Swiss rounds) "
        "and the current overall seeding. "
        "spirit: spirit ranking. leaderboard: top scorers, assisters and blockers."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "event_slug": SLUG_SCHEMA,
            "view": {"type": "string", "enum": VIEWS},
            "team_slug": SLUG_SCHEMA,
            "day": {"type": "string", "format": "date"},
        },
        "required": ["event_slug"],
        "additionalProperties": False,
    },
)
def get_tournament(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    slug = args["event_slug"]
    team_slug = args.get("team_slug")
    if problem := slug_problem(event_slug=slug, team_slug=team_slug):
        return problem
    view = args.get("view", "overview")
    if view == "schedule":
        return _schedule(ctx, slug, team_slug, args.get("day"))
    if view == "leaderboard":
        return _leaderboard(ctx, slug)
    response = call_api(ctx, "GET", "/api/tournament", query={"slug": slug})
    if not response.ok:
        return _missing(slug)
    tournament = response.data
    teams = [_team(t) for t in tournament["teams"]]
    if view == "standings":
        return _standings(ctx, slug, tournament, teams)
    if view == "spirit":
        return _spirit(slug, tournament, teams)
    event = tournament["event"]
    return ok(
        {
            "event_slug": slug,
            "title": event["title"],
            "start_date": event["start_date"],
            "end_date": event["end_date"],
            "location": event["location"],
            "status": _label(Tournament.Status, tournament["status"]),
            "series": event["series"]["name"] if event["series"] else None,
            "teams": teams,
        }
    )


def _missing(slug: str) -> ToolResult:
    return fail(f"No tournament with slug {slug}", hint="Find slugs with the search tool")


def _failed(response: ApiResponse, slug: str, team_slug: str | None) -> ToolResult:
    if team_slug and Tournament.objects.filter(event__slug=slug).exists():
        return fail(response.message)
    return _missing(slug)


def _schedule(ctx: ToolContext, slug: str, team_slug: str | None, day: str | None) -> ToolResult:
    path = f"/api/tournament/slug/{slug}/matches"
    if team_slug:
        path = f"/api/tournament/{slug}/team/{team_slug}/matches"
    response = call_api(ctx, "GET", path)
    if not response.ok:
        return _failed(response, slug, team_slug)
    matches = [_match(m) for m in response.data]
    if day:
        wanted = datetime.date.fromisoformat(day)
        zone = get_current_timezone()
        matches = [
            m
            for m in matches
            if m["time"]
            and datetime.datetime.fromisoformat(m["time"]).astimezone(zone).date() == wanted
        ]
    return ok(
        cap(
            {"event_slug": slug, "matches": matches},
            list_key="matches",
            hint="Narrow with team_slug or day",
        )
    )


def _standings(
    ctx: ToolContext, slug: str, tournament: dict[str, Any], teams: list[dict[str, Any]]
) -> ToolResult:
    by_id = {t["team_id"]: t for t in teams}

    def seeded(seeding: dict[str, int]) -> list[dict[str, Any]]:
        return [
            {"seed": int(seed), **by_id.get(team_id, {"team_id": team_id})}
            for seed, team_id in sorted(seeding.items(), key=lambda kv: int(kv[0]))
        ]

    def table(pool: dict[str, Any]) -> dict[str, Any]:
        rows = []
        for team_id, row in pool["results"].items():
            rows.append(
                {
                    "rank": row.get("rank"),
                    **by_id.get(int(team_id), {"team_id": int(team_id)}),
                    "wins": row.get("wins"),
                    "losses": row.get("losses"),
                    "draws": row.get("draws"),
                    "goals_for": row.get("GF"),
                    "goals_against": row.get("GA"),
                }
            )
        return {
            "name": pool["name"],
            "teams": sorted(rows, key=lambda r: (r["rank"] is None, r["rank"] or 0)),
        }

    def listed(path: str) -> list[dict[str, Any]]:
        response = call_api(ctx, "GET", path, query={"slug": slug})
        return list(response.data) if response.ok else []

    return ok(
        {
            "event_slug": slug,
            "current_seeding": seeded(tournament["current_seeding"]),
            "pools": [table(p) for p in listed("/api/tournament/pools")],
            "brackets": [
                {"name": b["name"], "seeding": seeded(b["current_seeding"])}
                for b in listed("/api/tournament/brackets")
            ],
            "position_pools": [table(p) for p in listed("/api/tournament/position-pools")],
        }
    )


def _spirit(slug: str, tournament: dict[str, Any], teams: list[dict[str, Any]]) -> ToolResult:
    by_id = {t["team_id"]: t for t in teams}
    ranking = [
        {
            "rank": r.get("rank"),
            **by_id.get(r["team_id"], {"team_id": r["team_id"]}),
            "points": r["points"],
            "self_points": r.get("self_points"),
        }
        for r in tournament["spirit_ranking"]
    ]
    return ok({"event_slug": slug, "teams": ranking})


def _leaderboard(ctx: ToolContext, slug: str) -> ToolResult:
    response = call_api(ctx, "GET", f"/api/tournament/{slug}/leaderboard")
    if not response.ok:
        return _missing(slug)
    out: dict[str, Any] = {"event_slug": slug}
    unlinked = False
    for key, count in (
        ("scores", "num_scores"),
        ("assists", "num_assists"),
        ("blocks", "num_blocks"),
        ("total", "num_total"),
    ):
        rows = response.data[key][:LEADERBOARD_ROWS]
        unlinked = unlinked or any(p["player_id"] is None for p in rows)
        out[key] = [
            {
                "player_id": p["player_id"],
                "full_name": full_name(p),
                "team_name": p["team_name"],
                key: p[count],
            }
            for p in rows
            if p["player_id"] is not None and count in p
        ]
    if unlinked:
        out["note"] = "Some players without a Hub profile are left out of these lists."
    return ok(out)


SPIRIT_PARTS = ("rules", "fouls", "fair", "positive", "communication", "total")


def _spirit_score(score: dict[str, Any] | None) -> dict[str, int] | None:
    return {part: score[part] for part in SPIRIT_PARTS} if score else None


@tool(
    "get_match",
    title="Get a match",
    description=(
        "One match by match_id: teams, score, status, field, time, spirit scores and a summary "
        "of live stats. has_live_stats says whether the match was tracked point by point."
    ),
    input_schema={
        "type": "object",
        "properties": {"match_id": {"type": "integer", "minimum": 1}},
        "required": ["match_id"],
        "additionalProperties": False,
    },
)
def get_match(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    match_id = args["match_id"]
    response = call_api(ctx, "GET", f"/api/match/{match_id}")
    if not response.ok:
        return fail(f"No match with match_id {match_id}", hint="Find match_id in the schedule view")
    match = response.data
    stats_response = call_api(ctx, "GET", f"/api/match/{match_id}/stats")
    stats = None
    if stats_response.ok:
        counts: dict[str, int] = {}
        for event in stats_response.data["events"]:
            label = _label(MatchEvent.EventType, event["type"])
            counts[label] = counts.get(label, 0) + 1
        stats = {
            "status": _label(MatchStats.Status, stats_response.data["status"]),
            "score_team_1": stats_response.data["score_team_1"],
            "score_team_2": stats_response.data["score_team_2"],
            "event_counts": counts,
        }
    return ok(
        {
            **_match(match),
            "has_live_stats": stats is not None,
            "stats": stats,
            "spirit": {
                "team_1": _spirit_score(match["spirit_score_team_1"]),
                "team_2": _spirit_score(match["spirit_score_team_2"]),
                "self_team_1": _spirit_score(match["self_spirit_score_team_1"]),
                "self_team_2": _spirit_score(match["self_spirit_score_team_2"]),
            },
        }
    )

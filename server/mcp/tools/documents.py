import datetime
import re
from typing import Any, cast

from django.conf import settings
from django.urls import reverse

from server.core.models import Player, Team, Vaccination
from server.mcp import upload
from server.mcp.confirm import confirm_then
from server.mcp.registry import ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import full_name
from server.subscription.api import may_see

NOT_ALLOWED = "Not allowed: {}"
DETAILS = {
    "college_id": ("expiry",),
    "vaccination": ("vaccine_name",),
    "new_team": ("name", "category", "state_ut", "city"),
}
MAX_LENGTH = {
    "name": cast(int, Team._meta.get_field("name").max_length),
    "city": cast(int, Team._meta.get_field("city").max_length),
    "category": 20,
    "state_ut": 5,
    "expiry": 10,
    "vaccine_name": 10,
}
PLAYER_KINDS = ("accreditation", "college_id", "vaccination")


def _problem(ctx: ToolContext, kind: str, args: dict[str, Any], details: dict[str, Any]) -> str:
    for name in DETAILS.get(kind, ()):
        if not str(details.get(name, "")).strip():
            return f"details.{name} is required for {kind}."
        if len(str(details[name])) > MAX_LENGTH[name]:
            return f"details.{name} must have at most {MAX_LENGTH[name]} characters."
    if kind in PLAYER_KINDS:
        player = Player.objects.filter(pk=args.get("player_id", 0)).first()
        if player is None:
            return "player_id is required, and must be a player you can see."
        if not may_see(ctx.user, player):
            return NOT_ALLOWED.format("you can only upload for yourself or your wards.")
    elif kind == "profile_pic":
        if not Player.objects.filter(user=ctx.user).exists():
            return "You have no player profile to put a picture on."
    elif (
        kind == "team_logo"
        and not Team.objects.filter(pk=args.get("team_id", 0), admins=ctx.user).exists()
    ):
        return NOT_ALLOWED.format("only a team admin can change the team's logo.")
    if kind == "college_id":
        expiry = str(details["expiry"])
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expiry):
                raise ValueError(expiry)
            datetime.date.fromisoformat(expiry)
        except ValueError:
            return "details.expiry must be a date like 2027-05-31."
    if kind == "vaccination" and details["vaccine_name"] not in Vaccination.VaccinationName.values:
        return (
            f"details.vaccine_name must be one of {', '.join(Vaccination.VaccinationName.values)}."
        )
    return ""


def _what(ctx: ToolContext, kind: str, args: dict[str, Any], details: dict[str, Any]) -> str:
    player = Player.objects.filter(pk=args.get("player_id", 0)).select_related("user").first()
    who = full_name(player.user) if player else ""
    match kind:
        case "accreditation":
            return f"Upload a WFDF certificate for {who}; it replaces the one on file"
        case "college_id":
            return (
                f"Upload a college ID for {who}, expiring {details['expiry']}; "
                "it replaces the one on file"
            )
        case "vaccination":
            return (
                f"Upload a vaccination certificate ({details['vaccine_name']}) for {who}; "
                "it replaces the one on file"
            )
        case "profile_pic":
            return "Replace your profile picture with the uploaded image"
        case "team_logo":
            team = Team.objects.get(pk=args["team_id"])
            return f"Replace the logo of {team.name} with the uploaded image"
    return (
        f"Create the team {details['name']} ({details['category']}, {details['city']}) "
        "with the uploaded logo"
    )


def _part(kind: str, args: dict[str, Any], details: dict[str, Any]) -> dict[str, Any] | None:
    match kind:
        case "accreditation":
            return {"player_id": args["player_id"]}
        case "college_id":
            return {"player_id": args["player_id"], "expiry": details["expiry"]}
        case "vaccination":
            return {
                "player_id": args["player_id"],
                "is_vaccinated": True,
                "name": details["vaccine_name"],
            }
        case "team_logo":
            return {"id": str(args["team_id"])}
        case "new_team":
            return {name: details[name] for name in DETAILS["new_team"]}
    return None


@tool(
    "create_upload_link",
    title="Create a file upload link",
    description=(
        "Make a one-time link, valid for 15 minutes, to upload a file to Hub. kind: accreditation "
        "(WFDF PDF), college_id, vaccination, profile_pic, team_logo, new_team. "
        "If you can run shell commands (a coding agent, say), run the returned curl "
        "command yourself with the user's file path, then tell them it's done; otherwise give "
        "them upload_url to open. details: expiry (college_id, YYYY-MM-DD), vaccine_name "
        "(vaccination: CVSHLD, CVXN, MDRN, SPTNK or JNJ), name, "
        "category, state_ut, city (new_team). Hub asks the user to confirm first."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": list(upload.KINDS)},
            "player_id": {"type": "integer"},
            "team_id": {"type": "integer"},
            "details": {"type": "object"},
        },
        "required": ["kind"],
        "additionalProperties": False,
    },
    writes=True,
)
def create_upload_link(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    kind = args["kind"]
    details = args.get("details", {})
    if problem := _problem(ctx, kind, args, details):
        return fail(problem)
    ids: dict[str, int] = {k: int(args[k]) for k in ("player_id", "team_id") if k in args}

    def mint() -> ToolResult:
        token = upload.mint(ctx.user.pk, kind, ids, _part(kind, args, details))
        url = settings.PUBLIC_URL + reverse("mcp-upload", args=[token])
        files = list(upload.KINDS[kind].files)
        flags = " ".join(f"-F {name}=@/path/to/{name}" for name in files)
        return ok(
            {
                "upload_url": url,
                "expires_in_seconds": upload.MAX_AGE,
                "files": files,
                "curl": f"curl {flags} '{url}'",
            }
        )

    return confirm_then(
        ctx,
        message=f"{_what(ctx, kind, args, details)}. Make a one-time upload link for it?",
        binding=args,
        action=mint,
    )

import datetime
import hashlib
from pathlib import Path
from typing import Any

from django.conf import settings

from server.core.models import Guardianship, Player, StatesUTs
from server.mcp.confirm import confirm_then
from server.mcp.dispatch import ApiResponse, call_api, denied, refuse
from server.mcp.pay import pay_link, unpaid_membership
from server.mcp.private import is_private
from server.mcp.registry import ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import full_name

DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "documents"
DOCUMENTS = {
    path.stem: path.read_text(encoding="utf-8") for path in sorted(DOCUMENTS_DIR.glob("*.md"))
}
LONG_TEXT = 3000
PROFILE_FIELDS = [
    "first_name",
    "last_name",
    "phone",
    "date_of_birth",
    "gender",
    "other_gender",
    "match_up",
    "city",
    "state_ut",
    "not_in_india",
    "occupation",
    "educational_institution",
]
COMMENTARY_FIELDS = [
    "jersey_number",
    "ultimate_origin",
    "ultimate_attraction",
    "ultimate_fav_role",
    "ultimate_fav_exp",
    "interests",
    "fun_fact",
]
STRING = {"type": "string", "minLength": 1, "maxLength": 100}
FIELD_SCHEMAS: dict[str, dict[str, Any]] = {
    "first_name": STRING,
    "last_name": STRING,
    "phone": {"type": "string", "minLength": 5, "maxLength": 20},
    "date_of_birth": {"type": "string", "format": "date"},
    "gender": {"enum": ["M", "F", "O"], "type": "string"},
    "other_gender": {"type": "string", "maxLength": 30},
    "match_up": {
        "enum": ["M", "F"],
        "type": "string",
        "description": "Who they match up against in mixed. Only needed when gender is O.",
    },
    "city": STRING,
    "state_ut": {"enum": sorted(StatesUTs.values), "type": "string"},
    "not_in_india": {"type": "boolean"},
    "occupation": {
        "enum": [
            "Student",
            "College-Student",
            "Business",
            "Government",
            "Non-profit",
            "Other",
            "Unemployed",
        ],
        "type": "string",
    },
    "educational_institution": STRING,
}
COMMENTARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "jersey_number": {"type": "integer", "minimum": 0},
        **{name: {"type": "string", "maxLength": 1000} for name in COMMENTARY_FIELDS[1:]},
    },
    "additionalProperties": False,
}
RELATIONS = {"MO": "mother", "FA": "father", "LG": "legal guardian"}
GUARDIAN_FIELDS = ["guardian_first_name", "guardian_last_name", "guardian_email", "guardian_phone"]
REQUIRED = ["first_name", "last_name", "phone", "date_of_birth", "gender", "match_up", "city"]
NEEDS = {
    "me": REQUIRED,
    "ward": [*REQUIRED, "relation"],
    "me_minor": [*REQUIRED, "relation", *GUARDIAN_FIELDS],
}
ROUTES = {
    "me": "/api/registration",
    "ward": "/api/registration/ward",
    "me_minor": "/api/registration/guardian",
}
KEY_POINTS = {
    "waiver_adult": [
        (
            "You accept the risks of taking part, including injury and communicable illness "
            "such as COVID-19, and you are responsible for your own safety."
        ),
        (
            "You will not take part if you had symptoms in the last 14 days, or you or your "
            "household were diagnosed in the last 30 days."
        ),
        (
            "You release India Ultimate, its officers, volunteers and sponsors from claims for "
            "loss or injury, and agree to indemnify them."
        ),
        "You consent to photos, video and live streams of you at India Ultimate events.",
    ],
    "waiver_minor": [
        (
            "You accept, for your ward, the risks of taking part, including injury and "
            "communicable illness such as COVID-19, and you are responsible for their safety."
        ),
        (
            "Your ward will not take part if they had symptoms in the last 14 days, or they or "
            "your household were diagnosed in the last 30 days."
        ),
        (
            "You release India Ultimate, its officers, volunteers and sponsors from claims for "
            "loss or injury to your ward, and agree to indemnify them."
        ),
        (
            "You confirm you are their parent or legal guardian and consent to photos, video "
            "and live streams of them at India Ultimate events."
        ),
    ],
    "code_of_conduct": [
        (
            "You will treat everyone with dignity and fairness, and not harass, bully, "
            "discriminate against or intimidate anyone."
        ),
        "You will put safety first, and raise concerns about unsafe behaviour promptly.",
        (
            "Abuse, any sexual or romantic behaviour involving anyone under 18, and hiding "
            "safeguarding concerns are strictly prohibited."
        ),
        (
            "Breaking the code can lead to removal from activities, suspension, a report to "
            "the authorities or legal action."
        ),
    ],
}
PATHS = {"waiver": "waiver", "coc": "code-of-conduct"}
HUB_ROUTES = {"waiver": "/api/waiver", "coc": "/api/code-of-conduct"}


def player_ids(ctx: ToolContext, args: dict[str, Any]) -> list[int] | ToolResult:
    """The player_id asked for, or the caller's own and their wards'."""
    if "player_id" in args:
        return [args["player_id"]]
    me = call_api(ctx, "GET", "/api/me")
    if not me.ok:
        return fail(me.message)
    return [p["id"] for p in [me.data["player"], *me.data["wards"]] if p]


def _player(ctx: ToolContext, player_id: int) -> ApiResponse:
    return call_api(ctx, "GET", f"/api/players/{player_id}")


def _show(day: str) -> str:
    return f"{datetime.date.fromisoformat(day):%-d %B %Y}"


def _missing(args: dict[str, Any], names: list[str]) -> ToolResult | None:
    absent = [name for name in names if args.get(name) in (None, "")]
    if absent:
        return fail(
            f"Missing: {', '.join(absent)}", hint="Ask the user for these, then call again."
        )
    return None


@tool(
    "create_profile",
    title="Create a player profile",
    description=(
        "Create a Hub player profile. for=me: the signed-in adult's own profile. "
        "for=ward: a profile for a child under 18 that the signed-in user is guardian of "
        "(relation required, the child's email optional). for=me_minor: the signed-in user is "
        "under 18 and names a guardian (relation and guardian_* required). Use whoami or "
        "get_readiness first to see whether a profile exists."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "for": {"type": "string", "enum": ["me", "ward", "me_minor"]},
            **{name: FIELD_SCHEMAS[name] for name in PROFILE_FIELDS if name != "date_of_birth"},
            "date_of_birth": FIELD_SCHEMAS["date_of_birth"],
            "email": {"type": "string", "maxLength": 254},
            "relation": {"type": "string", "enum": sorted(RELATIONS)},
            "guardian_first_name": STRING,
            "guardian_last_name": STRING,
            "guardian_email": {"type": "string", "maxLength": 254},
            "guardian_phone": {"type": "string", "minLength": 5, "maxLength": 20},
        },
        "required": ["for"],
        "additionalProperties": False,
    },
    writes=True,
)
def create_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    mode = args["for"]
    if args.get("gender") in ("M", "F"):
        args = {"match_up": args["gender"], **args}
    if problem := _missing(args, NEEDS[mode]):
        return problem
    body = {
        k: v
        for k, v in args.items()
        if k not in ("for", "confirmation") and (mode == "ward" or k != "email")
    }
    if mode != "me":
        body.setdefault("occupation", "Student")
    name = f"{args['first_name']} {args['last_name']}"
    born = f"{name}, {args['city']}"
    if mode == "me":
        message = f"Create your Hub player profile: {born}, on the account you're signed in with."
    elif mode == "ward":
        account = "using the email address given" if args.get("email") else "with no email address"
        message = (
            f"Create a player profile for {born}, a minor, with you as their "
            f"{RELATIONS[args['relation']]} and guardian. Hub creates an account for "
            f"{args['first_name']} {account}."
        )
    else:
        guardian = f"{args['guardian_first_name']} {args['guardian_last_name']}"
        message = (
            f"Create your player profile: {born}. Hub creates an account for your "
            f"{RELATIONS[args['relation']]} {guardian} as your guardian, with the email address given; "
            "they can log in with it to sign documents for you."
        )

    def action() -> ToolResult:
        response = call_api(ctx, "POST", ROUTES[mode], body=body)
        if not response.ok:
            return denied(response)
        return ok(
            {
                "done": True,
                "player_id": response.data["id"],
                "full_name": response.data["full_name"],
                "message": f"Created the profile for {response.data['full_name']}.",
                "next": "Call get_readiness for what is left before they can play.",
            }
        )

    return confirm_then(ctx, message=message, binding=args, action=action)


def _describe(field: str, old: Any, new: Any) -> str:
    if is_private(field):
        return f"{field}: changed"
    return f"{field}: {old if old not in (None, '') else '(empty)'} -> {new}"


@tool(
    "update_profile",
    title="Edit a player profile",
    description=(
        "Change fields on the profile of the signed-in user or one of their wards. Pass only "
        "the fields to change in changes; the rest stay as they are. commentary_info changes "
        "the commentator details (jersey number, origin and so on); the first time, it needs "
        "every field."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "player_id": {"type": "integer"},
            "changes": {
                "type": "object",
                "properties": {
                    **FIELD_SCHEMAS,
                    "commentary_info": COMMENTARY_SCHEMA,
                },
                "additionalProperties": False,
            },
        },
        "required": ["player_id", "changes"],
        "additionalProperties": False,
    },
    writes=True,
    destructive=True,
)
def update_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    changes = args["changes"]
    if not changes:
        return fail("changes is empty", hint="Name at least one field to change.")
    player_id = args["player_id"]
    current = _player(ctx, player_id)
    if not current.ok:
        return denied(current)
    if "accreditation" not in current.data:
        return refuse("only the player, their guardian or staff can edit a profile")
    data = current.data

    fields = {k: v for k, v in changes.items() if k != "commentary_info"}
    lines = [_describe(k, data.get(k), v) for k, v in fields.items() if data.get(k) != v]
    commentary: dict[str, Any] | None = None
    if "commentary_info" in changes:
        existing = {k: (data.get("commentary_info") or {}).get(k) for k in COMMENTARY_FIELDS}
        commentary = {**existing, **changes["commentary_info"]}
        if problem := _missing(commentary, COMMENTARY_FIELDS):
            return problem
        lines.append(
            "commentary info: "
            + ", ".join(k for k in changes["commentary_info"] if existing[k] != commentary[k])
        )
    if not lines:
        return ok({"done": True, "message": "Nothing to change: the profile already says that."})
    message = f"Change {data['full_name']}'s profile ({'; '.join(lines)})."

    def action() -> ToolResult:
        if fields:
            body = {k: data.get(k) for k in PROFILE_FIELDS} | fields | {"player_id": player_id}
            response = call_api(ctx, "PUT", "/api/registration", body=body)
            if not response.ok:
                return denied(response)
        if commentary is not None:
            response = call_api(
                ctx, "POST", "/api/commentary-info", body={**commentary, "player_id": player_id}
            )
            if not response.ok:
                return denied(response)
        return ok({"done": True, "player_id": player_id, "message": "Profile updated."})

    return confirm_then(ctx, message=message, binding=args, action=action)


def _documents_of(data: dict[str, Any]) -> dict[str, Any]:
    subscription = data.get("subscription") or {}
    accreditation = data.get("accreditation") or {}
    college_id = data.get("college_id")
    vaccination = data.get("vaccination")
    return {
        "player_id": data["id"],
        "full_name": data["full_name"],
        "membership": {
            "active": bool(subscription.get("is_active")),
            "tier": subscription.get("tier"),
            "tier_name": subscription.get("tier_name"),
            "season_name": subscription.get("season_name"),
            "start_date": subscription.get("start_date"),
            "end_date": subscription.get("end_date"),
        },
        "waiver": {
            "signed": bool(subscription.get("waiver_signed_at")),
            "signed_by": subscription.get("waiver_signed_by"),
            "signed_at": subscription.get("waiver_signed_at"),
            "valid": bool(subscription.get("waiver_valid")),
        },
        "coc": {
            "agreed": bool(subscription.get("coc_agreed")),
            "agreed_by": subscription.get("coc_agreed_by"),
            "agreed_at": subscription.get("coc_agreed_at"),
        },
        "accreditation": {
            "present": bool(accreditation),
            "level": accreditation.get("level"),
            "expiry": accreditation.get("expiry_date"),
            "valid": bool(accreditation.get("is_valid")),
        },
        "college_id": {
            "present": college_id is not None,
            "expiry": college_id["expiry"] if college_id else None,
            "images_present": bool(
                college_id
                and college_id.get("card_front")
                and college_id.get("card_back")
                and not college_id.get("images_removed_at")
            ),
        },
        "vaccination": {"present": vaccination is not None},
        "profile_picture": {"present": bool(data.get("profile_pic_url"))},
    }


@tool(
    "get_documents",
    title="My documents and membership",
    description=(
        "Stored documents and their validity (not whether someone may play an event: see get_readiness) for the signed-in user and their wards (or one player_id): membership tier and "
        "validity, waiver and code of conduct signing, WFDF accreditation, college ID, "
        "vaccination and profile picture. Shows status only, never the files."
    ),
    input_schema={
        "type": "object",
        "properties": {"player_id": {"type": "integer"}},
        "additionalProperties": False,
    },
)
def get_documents(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    ids = player_ids(ctx, args)
    if isinstance(ids, ToolResult):
        return ids
    players = []
    for player_id in ids:
        response = _player(ctx, player_id)
        if not response.ok:
            return denied(response)
        if "accreditation" not in response.data:
            return refuse("only the player, their guardian or staff can see their documents")
        players.append(_documents_of(response.data))
    return ok({"players": players})


def _text_of(
    document: str, minor: bool, name: str, subscription: dict[str, Any]
) -> tuple[str, str]:
    key = "code_of_conduct" if document == "coc" else f"waiver_{'minor' if minor else 'adult'}"
    text = DOCUMENTS[key]
    for placeholder, value in {
        "{player_name}": name,
        "{start_date}": _show(subscription["start_date"]),
        "{end_date}": _show(subscription["end_date"]),
    }.items():
        text = text.replace(placeholder, value)
    return key, text


def _refusal(ctx: ToolContext, player: Player, document: str) -> str | None:
    """Hub's own answer to a signer who may not sign, before asking them to confirm."""
    waiver = document == "waiver"
    if player.is_minor:
        if ctx.user == player.user:
            return (
                "Waiver can only signed by a guardian"
                if waiver
                else "Only your guardian can agree for you"
            )
        guardianship = Guardianship.objects.filter(player=player).first()
        if guardianship is None:
            return "Guardian does not exist for player"
        if guardianship.user_id != ctx.user.pk:
            return "Only this player's guardian can " + (
                "sign their waiver" if waiver else "agree for them"
            )
        return None
    if ctx.user == player.user:
        return None
    return f"Only {full_name(player.user)} can " + (
        "sign their waiver" if waiver else "agree to their code of conduct"
    )


@tool(
    "sign_document",
    title="Sign the waiver or code of conduct",
    description=(
        "Sign this season's waiver or agree to the code of conduct for the signed-in user, "
        "or for a ward who is under 18. Hub does not let a guardian sign for an adult. A "
        "membership is needed first. The user is shown the text (or key points and a link) "
        "and must say yes."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "player_id": {"type": "integer"},
            "document": {"type": "string", "enum": ["waiver", "coc"]},
        },
        "required": ["player_id", "document"],
        "additionalProperties": False,
    },
    writes=True,
)
def sign_document(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    player_id, document = args["player_id"], args["document"]
    response = _player(ctx, player_id)
    if not response.ok:
        return denied(response)
    data = response.data
    if "accreditation" not in data:
        return refuse("only the player, their guardian or staff can see this player")
    subscription = data.get("subscription")
    label = "waiver" if document == "waiver" else "code of conduct"
    if not subscription:
        if order_id := unpaid_membership(ctx.user, player_id):
            return fail(
                f"{data['full_name']}'s membership order is waiting to be paid. The {label} "
                "can be signed once it is.",
                pay_url=pay_link(order_id),
                hint="Give the person pay_url, then sign after they have paid.",
            )
        return fail(
            f"{data['full_name']} needs a membership before the {label} can be signed.",
            hint=f"get_membership_options for player_id {player_id}, then buy_membership.",
        )
    player = Player.objects.select_related("user").get(id=player_id)
    if problem := _refusal(ctx, player, document):
        return fail(problem)
    if subscription["waiver_valid" if document == "waiver" else "coc_agreed"]:
        return ok({"done": True, "message": f"The {label} is already signed for this season."})

    minor = player.is_minor
    key, text = _text_of(document, minor, data["full_name"], subscription)
    me = player.user == ctx.user
    season = str(subscription["season_name"]).removeprefix("Season ")
    summary = (
        f"Sign the {season} {label} for {data['full_name']} "
        f"({'you' if me else 'your ward'}) as {full_name(ctx.user)}"
    )
    link = f"{settings.PUBLIC_URL}/{PATHS[document]}/{player_id}"
    if len(text) > LONG_TEXT:
        points = "\n".join(f"- {point}" for point in KEY_POINTS[key])
        message = f"{summary}.\nKey points:\n{points}\nFull text: {link}"
    else:
        message = f"{summary}.\n\n{text}"
    binding = {**args, "shown_sha256": hashlib.sha256(text.encode()).hexdigest()}

    def action() -> ToolResult:
        signed = call_api(ctx, "POST", HUB_ROUTES[document], body={"player_id": player_id})
        if not signed.ok:
            return denied(signed)
        return ok({"done": True, "player_id": player_id, "message": f"Signed: {summary}."})

    result = confirm_then(ctx, message=message, binding=binding, action=action)
    if isinstance(result.data, dict) and "needs_confirmation" in result.data:
        result.data["full_text"] = text
    return result

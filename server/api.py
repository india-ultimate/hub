import contextlib
import datetime
import hashlib
import io
from base64 import b32encode
from typing import Any, cast

import pyotp
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.base_user import AbstractBaseUser
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models import Count, F, Q, QuerySet, Value
from django.db.models.functions import Concat
from django.db.utils import IntegrityError
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from ninja import File, NinjaAPI, UploadedFile
from ninja.pagination import PageNumberPagination, paginate
from ninja.security import django_auth

from server.core.models import (
    Accreditation,
    CollegeId,
    CommentaryInfo,
    Guardianship,
    Player,
    Team,
    UCPerson,
    User,
    Vaccination,
)
from server.lib.membership import get_membership_status
from server.membership.models import Membership
from server.passkey_utils import PassKeyClient
from server.schema import (
    AccreditationFormSchema,
    AccreditationSchema,
    CollegeIdFormSchema,
    CollegeIdSchema,
    CommentaryInfoFormSchema,
    CommentaryInfoSchema,
    ContactFormSchema,
    Credentials,
    GuardianshipFormSchema,
    NotVaccinatedFormSchema,
    OTPLoginCredentials,
    OTPRequestCredentials,
    OTPRequestResponse,
    PasskeyRequestSchema,
    PasskeyResponseSchema,
    PlayerFormSchema,
    PlayerSchema,
    PlayerTinySchema,
    RegistrationGuardianSchema,
    RegistrationOthersSchema,
    RegistrationSchema,
    RegistrationWardSchema,
    Response,
    TeamCreateSchema,
    TeamSchema,
    TeamUpdateSchema,
    TopScoreCredentials,
    UserAccessSchema,
    UserFormSchema,
    UserMinSchema,
    UserSchema,
    VaccinatedFormSchema,
    VaccinationSchema,
    WaiverFormSchema,
)
from server.season.api import router as season_router
from server.series.api import router as series_router
from server.series.models import SeriesRegistration
from server.top_score_utils import TopScoreClient
from server.tournament.match_stats_min import (
    handle_all_events,
    handle_full_time,
    handle_half_time,
    handle_switch_offense,
    handle_undo,
)
from server.tournament.models import (
    Bracket,
    CrossPool,
    Event,
    Match,
    MatchEvent,
    MatchScore,
    MatchStats,
    Pool,
    PositionPool,
    Registration,
    Tournament,
    TournamentField,
    UCRegistration,
)
from server.tournament.schema import (
    AddOrRemoveTeamRegistrationSchema,
    AddToRosterSchema,
    BracketCreateSchema,
    BracketSchema,
    CrossPoolSchema,
    EventSchema,
    MatchCreateSchema,
    MatchEventCreateSchema,
    MatchSchema,
    MatchScoreSchema,
    MatchStatsCreateSchema,
    MatchStatsSchema,
    MatchUpdateSchema,
    PoolCreateSchema,
    PoolSchema,
    PositionPoolCreateSchema,
    PositionPoolSchema,
    SpiritScoreSubmitSchema,
    TournamentCreateFromEventSchema,
    TournamentCreateSchema,
    TournamentFieldCreateSchema,
    TournamentFieldSchema,
    TournamentFieldUpdateSchema,
    TournamentPlayerRegistrationSchema,
    TournamentPlayerRegistrationUpdateSchema,
    TournamentRulesSchema,
    TournamentSchema,
    TournamentUpdateSeedingSchema,
    UCRegistrationSchema,
)
from server.tournament.utils import (
    can_register_player_to_series_event,
    create_bracket_matches,
    create_pool_matches,
    create_position_pool_matches,
    create_spirit_scores,
    get_bracket_match_name,
    get_default_rules,
    is_submitted_scores_equal,
    populate_fixtures,
    update_match_score_and_results,
    update_tournament_spirit_rankings,
    user_tournament_teams,
    validate_new_pool,
    validate_seeds_and_teams,
)
from server.transaction.api import router as transaction_router
from server.types import message_response
from server.utils import (
    if_dates_are_not_in_order,
    if_today,
    is_today_in_between_dates,
)

api = NinjaAPI(auth=django_auth, csrf=True)


class AuthenticatedHttpRequest(HttpRequest):
    user: User


# Routers
api.add_router("/seasons", season_router)
api.add_router("/series/", series_router)
api.add_router("/transactions", transaction_router)


# User #########


@api.get("/me", response={200: UserSchema})
def me(request: AuthenticatedHttpRequest) -> User:
    return request.user


@api.get(
    "/me/access",
    response={200: UserAccessSchema, 400: Response, 401: Response},
)
def me_access(
    request: AuthenticatedHttpRequest, tournament_slug: str
) -> tuple[int, dict[str, bool | set[int] | str | int | None]]:
    try:
        event = Event.objects.get(slug=tournament_slug)
        tournament = Tournament.objects.get(event=event)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}
    except Event.DoesNotExist:
        return 400, {"message": "Event does not exist"}

    player_team_id, admin_team_ids = user_tournament_teams(tournament, request.user)

    return 200, {
        "is_staff": request.user.is_staff,
        "is_tournament_admin": request.user.is_tournament_admin,
        "playing_team_id": player_team_id,
        "admin_team_ids": admin_team_ids,
        "is_tournament_volunteer": request.user in tournament.volunteers.all(),
    }


# Users ##########


@api.get("/users/search", response={200: list[UserMinSchema]})
def search_users(request: AuthenticatedHttpRequest, text: str = "") -> QuerySet[User]:
    text = text.strip().lower()
    return (
        User.objects.annotate(full_name=Concat("first_name", Value(" "), "last_name"))
        .filter(Q(full_name__icontains=text) | Q(username__icontains=text))
        .order_by("full_name")
    )


# Players ##########


@api.get("/players")
def list_players(
    request: AuthenticatedHttpRequest, full_schema: bool = False
) -> list[PlayerTinySchema | PlayerSchema]:
    players = Player.objects.all()
    is_staff = request.user.is_staff
    if is_staff and full_schema:
        return [PlayerSchema.from_orm(p) for p in players]
    else:
        return [PlayerTinySchema.from_orm(p) for p in players]


@api.get("/players/search", response={200: list[PlayerTinySchema]})
@paginate(PageNumberPagination, page_size=5)
def search_players(request: AuthenticatedHttpRequest, text: str = "") -> QuerySet[Player]:
    text = text.strip().lower()
    return (
        Player.objects.annotate(full_name=Concat("user__first_name", Value(" "), "user__last_name"))
        .filter(Q(full_name__icontains=text) | Q(user__username__icontains=text))
        .order_by("full_name")
    )


# Teams #########
@api.get("/teams", auth=None, response={200: list[TeamSchema]})
def list_teams(request: AuthenticatedHttpRequest) -> QuerySet[Team]:
    return Team.objects.all().order_by("name")


@api.get("/teams/search", auth=None, response={200: list[TeamSchema]})
@paginate(PageNumberPagination, page_size=10)
def search_teams(request: AuthenticatedHttpRequest, text: str = "") -> QuerySet[Team]:
    return Team.objects.filter(name__icontains=text.lower()).order_by("name")


@api.get("/team/{team_slug}", auth=None, response={200: TeamSchema, 400: Response})
def get_team(
    request: AuthenticatedHttpRequest, team_slug: str
) -> tuple[int, Team | message_response]:
    try:
        team = Team.objects.get(slug=team_slug)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    return 200, team


@api.post("/teams/edit", response={200: TeamSchema, 400: Response})
def update_team(
    request: AuthenticatedHttpRequest,
    team_details: TeamUpdateSchema,
    image: UploadedFile | None = File(None),  # noqa: B008
) -> tuple[int, Team | message_response]:
    try:
        team = Team.objects.get(id=team_details.id)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    if request.user not in team.admins.all():
        return 400, {"message": "User not an admin of the team"}

    if team_details.admin_ids is not None and len(team_details.admin_ids) == 0:
        return 400, {"message": "Admin IDs cant be empty"}

    if team_details.category is not None:
        team.category = team_details.category
    if team_details.state_ut is not None:
        team.state_ut = team_details.state_ut
    if team_details.city is not None:
        team.city = team_details.city
    if image is not None:
        team.image = image

    team.save()

    if team_details.admin_ids is not None:
        admins = User.objects.filter(id__in=team_details.admin_ids)
        team.admins.add(*admins)

    return 200, team


@api.post("/teams", response={200: TeamSchema, 400: Response})
def create_team(
    request: AuthenticatedHttpRequest,
    team_details: TeamCreateSchema,
    image: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, Team | message_response]:
    if not image:
        return 400, {"message": "Team logo needs to be uploaded!"}

    team = Team(
        name=team_details.name,
        category=team_details.category,
        state_ut=team_details.state_ut,
        city=team_details.city,
        image=image,
    )
    team.save()
    team.admins.add(request.user)

    return 200, team


# Login #########


@api.post("/login", auth=None, response={200: UserSchema, 403: Response})
def api_login(
    request: HttpRequest, credentials: Credentials
) -> tuple[int, AbstractBaseUser | message_response]:
    user = authenticate(
        request, username=credentials.username.strip().lower(), password=credentials.password
    )
    if user is not None:
        login(request, user)
        return 200, user
    else:
        return 403, {"message": "Invalid credentials"}


@api.post("/logout", response={200: Response})
@csrf_exempt
def api_logout(request: AuthenticatedHttpRequest) -> tuple[int, message_response]:
    logout(request)
    return 200, {"message": "Logged out"}


def get_email_hash(email: str) -> str:
    email_hash = hashlib.sha256()
    email_hash.update(email.encode("utf-8"))
    email_hash.update(settings.OTP_EMAIL_HASH_KEY.encode("utf-8"))
    return b32encode(email_hash.hexdigest().encode("utf-8")).decode("utf-8")


@api.post("/send-otp", auth=None, response={200: OTPRequestResponse})
def get_otp(
    request: HttpRequest, credentials: OTPRequestCredentials
) -> tuple[int, dict[str, int | str]]:
    credentials.email = credentials.email.strip().lower()
    email_hash = get_email_hash(credentials.email)
    totp = pyotp.TOTP(email_hash)
    current_ts = int(now().timestamp())
    otp = totp.generate_otp(current_ts)

    subject = "OTP to Sign in to India Ultimate Hub"
    html_message = render_to_string("otp_email.html", {"otp": otp})
    plain_message = strip_tags(html_message)
    from_email = settings.EMAIL_HOST_USER
    to = credentials.email

    mail.send_mail(subject, plain_message, from_email, [to], html_message=html_message)

    return 200, {"otp_ts": current_ts}


@api.post("/otp-login", auth=None, response={200: UserSchema, 403: Response, 404: Response})
def otp_login(
    request: HttpRequest, credentials: OTPLoginCredentials
) -> tuple[int, User | message_response]:
    credentials.email = credentials.email.strip().lower()
    email_hash = get_email_hash(credentials.email)
    totp = pyotp.TOTP(email_hash)
    actual_otp = totp.generate_otp(credentials.otp_ts)

    if actual_otp == credentials.otp:
        user, created = User.objects.get_or_create(
            email=credentials.email, username=credentials.email
        )
        request.user = user
        login(request, user)
        return 200, user

    return 403, {"message": "Invalid OTP"}


passkey_client = PassKeyClient()


@api.post("/passkey/create/start", response={200: PasskeyResponseSchema, 400: Response})
def passkey_start_creation(request: AuthenticatedHttpRequest) -> tuple[int, message_response]:
    data, error, _ = passkey_client.start_registration(str(request.user.id), request.user.username)

    if error:
        return 400, {"message": error}

    return 200, {"passkey_response": data}


@api.post("/passkey/create/finish", response={200: Response, 400: Response})
def passkey_finish_creation(
    request: AuthenticatedHttpRequest, body: PasskeyRequestSchema
) -> tuple[int, message_response]:
    data, error, _ = passkey_client.finish_registration(body.passkey_request)

    if error:
        return 400, {"message": error}

    return 200, {"message": "Success"}


@api.post("/passkey/login/start", auth=None, response={200: PasskeyResponseSchema, 400: Response})
def passkey_start_login(request: HttpRequest) -> tuple[int, message_response]:
    data, error, _ = passkey_client.start_login()

    if error:
        return 400, {"message": error}

    return 200, {"passkey_response": data}


@api.post("/passkey/login/finish", auth=None, response={200: UserSchema, 400: Response})
def passkey_finish_login(
    request: HttpRequest, body: PasskeyRequestSchema
) -> tuple[int, User | message_response]:
    data, error, user_id = passkey_client.finish_login(body.passkey_request)

    if error:
        return 400, {"message": error}

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return 400, {"message": "User does not exist"}

    request.user = user
    login(request, user)
    return 200, user


# Registration #########


@api.post("/registration", response={200: PlayerSchema, 400: Response})
def register_self(
    request: AuthenticatedHttpRequest, registration: RegistrationSchema
) -> tuple[int, Player | message_response]:
    return do_register(request.user, registration)


@api.put("/registration", response={200: PlayerSchema, 400: Response})
def edit_registration(
    request: AuthenticatedHttpRequest, registration: RegistrationSchema
) -> tuple[int, Player | message_response]:
    if not registration.player_id:
        return 400, {"message": "Need a player ID to edit profile information"}

    try:
        player = Player.objects.get(id=registration.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    player_data = PlayerFormSchema(**registration.dict()).dict()
    player_data["id"] = registration.player_id
    for key, value in player_data.items():
        setattr(player, key, value)

    try:
        player.full_clean()
    except ValidationError as e:
        return 400, {"message": str(e)}
    else:
        player.save()
        player.refresh_from_db()

    user_data = UserFormSchema(**registration.dict()).dict()
    for attr, value in user_data.items():
        setattr(player.user, attr, value)
    player.user.save()

    return 200, player


def do_register(
    user: User,
    registration: RegistrationSchema | RegistrationOthersSchema | RegistrationWardSchema,
    guardian: User | None = None,
) -> tuple[int, Player | message_response]:
    try:
        Player.objects.get(user=user)
        return 400, {"message": "Player already exists"}
    except Player.DoesNotExist:
        pass

    player_data = PlayerFormSchema(**registration.dict()).dict()
    player = Player(**player_data, user=user)
    try:
        player.full_clean()
    except ValidationError as e:
        return 400, {"message": str(e)}

    if player.is_minor and not guardian:
        return 400, {"message": "Minors need to have a guardian! Use the form for minors"}
    if not player.is_minor and guardian:
        return 400, {"message": "Only minors can have a guardian! Use the form for adults"}

    player.save()

    user_data = UserFormSchema(**registration.dict()).dict()
    for attr, value in user_data.items():
        setattr(user, attr, value)
    user.save()

    if player.ultimate_central_id is None:
        try:
            person = UCPerson.objects.get(email=user.email.strip().lower())
        except UCPerson.DoesNotExist:
            pass
        else:
            player.ultimate_central_id = person.id
            with contextlib.suppress(IntegrityError):
                player.save(update_fields=["ultimate_central_id"])

    if guardian:
        g = cast(GuardianshipFormSchema, registration)
        Guardianship.objects.create(
            user=guardian,
            player=player,
            relation=g.relation,  # type: ignore[attr-defined]
        )

    return 200, player


@api.post("/registration/others", response={200: PlayerSchema, 400: Response})
def register_others(
    request: AuthenticatedHttpRequest, registration: RegistrationOthersSchema
) -> tuple[int, Player | message_response]:
    user, created = User.objects.get_or_create(
        username=registration.email.strip().lower(),  # type: ignore[attr-defined]
        defaults={
            "email": registration.email.strip().lower(),  # type: ignore[attr-defined]
            "phone": registration.phone,  # type: ignore[attr-defined]
            "first_name": registration.first_name,  # type: ignore[attr-defined]
            "last_name": registration.last_name,  # type: ignore[attr-defined]
        },
    )
    return do_register(user, registration)


@api.post("/registration/ward", response={200: PlayerSchema, 400: Response})
def register_ward(
    request: AuthenticatedHttpRequest, registration: RegistrationWardSchema
) -> tuple[int, Player | message_response]:
    email = registration.email.strip().lower() if registration.email else None  # type: ignore[attr-defined]

    if request.user.email == email:
        return 400, {"message": "Use the players form instead of the guardians form"}

    if email is None:
        email = slugify(f"{registration.first_name} {registration.last_name}")  # type: ignore[attr-defined]
    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            "email": email,
            "phone": registration.phone,  # type: ignore[attr-defined]
            "first_name": registration.first_name,  # type: ignore[attr-defined]
            "last_name": registration.last_name,  # type: ignore[attr-defined]
        },
    )
    return do_register(user, registration, guardian=request.user)


@api.post("/registration/guardian", response={200: PlayerSchema, 400: Response})
def register_guardian(
    request: AuthenticatedHttpRequest, registration: RegistrationGuardianSchema
) -> tuple[int, Player | message_response]:
    email = registration.guardian_email.strip().lower()
    if request.user.email == email:
        return 400, {"message": "Use the guardians form instead of the players form"}

    user, _ = User.objects.get_or_create(
        username=email,
        defaults={
            "email": email,
            "phone": registration.guardian_phone,
            "first_name": registration.guardian_first_name,
            "last_name": registration.guardian_last_name,
        },
    )
    return do_register(request.user, registration, guardian=user)


# Events ##########


@api.get("/events", auth=None, response={200: list[EventSchema]})
def list_events(request: AuthenticatedHttpRequest, include_all: bool = False) -> QuerySet[Event]:
    today = now().date()
    return Event.objects.all() if include_all else Event.objects.filter(start_date__gte=today)


# Registrations ##########


@api.get(
    "/registrations/tournament/{tournament_id}",
    response={200: list[TournamentPlayerRegistrationSchema], 400: Response, 404: Response},
)
def list_registrations_for_tournament(
    request: AuthenticatedHttpRequest, tournament_id: int
) -> tuple[int, QuerySet[Registration] | dict[str, str]]:
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 404, {"message": f"Tournament with {tournament} not found."}

    registrations = Registration.objects.filter(event=tournament.event)

    return 200, registrations


@api.get(
    "/registrations/{event_id}",
    response={200: list[UCRegistrationSchema], 400: Response, 404: Response},
)
def list_registrations(
    request: AuthenticatedHttpRequest, event_id: int
) -> tuple[int, QuerySet[UCRegistration] | dict[str, str]]:
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return 404, {"message": f"Event with {event_id} not found."}

    registrations = UCRegistration.objects.filter(event=event)

    return 200, registrations


# Memberships ##########


@api.post("/check-memberships", response={200: list[dict[str, Any]], 400: Response, 401: Response})
def check_membership_status(
    request: AuthenticatedHttpRequest,
    info_csv: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, message_response] | tuple[int, list[dict[str, Any]]]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can check membership status"}

    if not info_csv.name or not info_csv.name.endswith(".csv"):
        return 400, {"message": "Please upload a CSV file!"}

    text = info_csv.read().decode("utf-8")
    data = get_membership_status(io.StringIO(text))
    if data is None:
        return 400, {"message": "Could not file an Email header in the CSV!"}

    return 200, list(data.values())


# Vaccination ##########


@api.post("/vaccination", response={200: VaccinationSchema, 400: Response})
def vaccination(
    request: AuthenticatedHttpRequest,
    vaccination: VaccinatedFormSchema | NotVaccinatedFormSchema,
    certificate: UploadedFile | None = File(None),  # noqa: B008
) -> tuple[int, Vaccination | message_response]:
    if vaccination.is_vaccinated and not certificate:
        return 400, {"message": "Certificate needs to be uploaded!"}

    try:
        player = Player.objects.get(id=vaccination.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    try:
        vaccine = player.vaccination
        edit = True
    except Vaccination.DoesNotExist:
        edit = False

    vaccination_data = vaccination.dict()
    vaccination_data["certificate"] = certificate
    vaccination_data["player"] = player
    if not edit:
        vaccine = Vaccination(**vaccination_data)
    else:
        vaccine.certificate = certificate
        vaccine.is_vaccinated = vaccination_data.get("is_vaccinated", False)
        vaccine.name = vaccination_data.get("name")
        vaccine.explain_not_vaccinated = vaccination_data.get("explain_not_vaccinated", "")

    vaccine.full_clean()
    vaccine.save()
    return 200, vaccine


# Accreditation ##########


@api.post("/accreditation", response={200: AccreditationSchema, 400: Response})
def accreditation(
    request: AuthenticatedHttpRequest,
    accreditation: AccreditationFormSchema,
    certificate: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, Accreditation | message_response]:
    if not certificate:
        return 400, {"message": "Certificate needs to be uploaded!"}

    try:
        player = Player.objects.get(id=accreditation.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    try:
        acc = player.accreditation
        edit = True
    except Accreditation.DoesNotExist:
        edit = False

    accreditation_data = accreditation.dict()
    accreditation_data["certificate"] = certificate
    accreditation_data["player"] = player
    accreditation_data["is_valid"] = False

    if not edit:
        acc = Accreditation(**accreditation_data)
    else:
        acc.certificate = certificate
        acc.date = accreditation_data.get("date", None)
        acc.level = accreditation_data.get("level", Accreditation.AccreditationLevel.STANDARD)

    try:
        acc.full_clean()
    except ValidationError as e:
        return 400, {"message": " ".join(e.messages)}

    acc.save()
    return 200, acc


# College ID Card ##########


@api.post("/college-id", response={200: CollegeIdSchema, 400: Response})
def college_id(
    request: AuthenticatedHttpRequest,
    college_id: CollegeIdFormSchema,
    card_front: UploadedFile = File(...),  # noqa: B008
    card_back: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, CollegeId | message_response]:
    if not card_front:
        return 400, {"message": "ID Card front side needs to be uploaded!"}
    if not card_back:
        return 400, {"message": "ID Card back side needs to be uploaded!"}

    try:
        player = Player.objects.get(id=college_id.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    try:
        c_id = player.college_id
        edit = True
    except CollegeId.DoesNotExist:
        edit = False

    college_id_data = college_id.dict()
    college_id_data["card_front"] = card_front
    college_id_data["card_back"] = card_back
    college_id_data["player"] = player

    # card_front_content = card_front.read()
    # img = Image.open(io.BytesIO(card_front_content))
    # img = img.resize((640, 480), Image.LANCZOS)

    # img_byte_arr = io.BytesIO()
    # img.save(img_byte_arr, format="PNG", optimize=True, quality=85)

    # payload = {"apikey": OCR_API_KEY, "filetype": "PNG"}
    # r = requests.post(
    #     "https://api.ocr.space/parse/image",
    #     files={"filename": img_byte_arr.getvalue()},
    #     data=payload,
    #     timeout=10,
    # )
    # resp = r.json()
    # if (
    #     not resp["IsErroredOnProcessing"]
    #     and len(resp["ParsedResults"]) > 0
    #     and resp["ParsedResults"][0]["ParsedText"]
    # ):
    #     collection = [player.user.get_full_name(), player.educational_institution]
    #     fuzz_result = process.extract(
    #         resp["ParsedResults"][0]["ParsedText"], collection, scorer=fuzz.token_set_ratio
    #     )
    #     college_id_data["ocr_name"] = fuzz_result[0][1]
    #     college_id_data["ocr_college"] = fuzz_result[1][1]

    if not edit:
        c_id = CollegeId(**college_id_data)
    else:
        c_id.card_front = card_front
        c_id.card_back = card_back
        c_id.expiry = college_id_data.get("expiry", None)
        c_id.ocr_name = college_id_data.get("ocr_name", None)
        c_id.ocr_college = college_id_data.get("ocr_college", None)

    try:
        c_id.full_clean()
    except ValidationError as e:
        return 400, {"message": " ".join(e.messages)}

    c_id.save()
    return 200, c_id


# Commentary Info #########


@api.post("/commentary-info", response={200: CommentaryInfoSchema, 400: Response})
def upsert_commentary_info(
    request: AuthenticatedHttpRequest, commentary_info: CommentaryInfoFormSchema
) -> tuple[int, CommentaryInfo | message_response]:
    try:
        player = Player.objects.get(id=commentary_info.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    com_info, created = CommentaryInfo.objects.update_or_create(
        player=player, defaults=commentary_info.dict()
    )
    return 200, com_info


# Waiver ##########


@api.post("/waiver", response={200: PlayerSchema, 400: Response})
def waiver(
    request: AuthenticatedHttpRequest, waiver: WaiverFormSchema
) -> tuple[int, Player] | tuple[int, message_response]:
    try:
        player = Player.objects.get(id=waiver.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    try:
        membership = player.membership
    except Membership.DoesNotExist:
        return 400, {"message": "Player does not have a membership"}

    if player.is_minor:
        if request.user == player.user:
            return 400, {"message": "Waiver can only signed by a guardian"}

        try:
            guardianship = player.guardianship
        except Guardianship.DoesNotExist:
            return 400, {"message": "Guardian does not exist for player"}

        if guardianship.user.id != request.user.id:
            return 400, {
                "message": f"Only Guardian - {guardianship.user.username} can sign this player's waiver"
            }

    membership.waiver_signed_by = request.user
    membership.waiver_signed_at = now()
    membership.waiver_valid = True
    membership.save(update_fields=["waiver_signed_by", "waiver_signed_at", "waiver_valid"])

    return 200, player


# UPAI ID ##########


@api.post(
    "/upai/me", response={200: PlayerSchema, 403: PlayerTinySchema, 400: Response, 404: Response}
)
def upai_person(
    request: AuthenticatedHttpRequest, credentials: TopScoreCredentials
) -> tuple[int, Player] | tuple[int, message_response]:
    try:
        player = Player.objects.get(id=credentials.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    client = TopScoreClient(credentials.username, credentials.password)
    person = client.get_person()
    if person is None or person["person_id"] is None:
        return 404, {"message": "Failed to fetch person information from Ultimate Central"}
    person_id = person["person_id"]
    if person_id:
        player.ultimate_central_id = person_id
        try:
            player.full_clean()
        except ValidationError as e:
            other_player = Player.objects.filter(ultimate_central_id=person_id).first()
            if other_player is None:
                return 400, {"message": e.messages[0]}
            else:
                return 403, other_player
        else:
            player.save()
            # Populate teams for the player from UC Registration data
            team_ids = UCRegistration.objects.filter(person_id=person_id).values_list(
                "team_id", flat=True
            )
            for team_id in set(team_ids):
                player.teams.add(team_id)

    return 200, player


# Tournaments ##########


@api.get("/tournaments", auth=None, response={200: list[TournamentSchema]})
def get_all_tournaments(request: AuthenticatedHttpRequest) -> tuple[int, QuerySet[Tournament]]:
    """Get tournaments, most recently started tournament first"""
    return 200, Tournament.objects.all().order_by("-event__start_date")


@api.get("/tournament", auth=None, response={200: TournamentSchema, 400: Response})
def get_tournament(
    request: AuthenticatedHttpRequest, id: int | None = None, slug: str | None = None
) -> tuple[int, Tournament | message_response]:
    if id is None and slug is None:
        return 400, {"message": "Need either tournament id or slug"}
    try:
        if id is not None:
            tournament = Tournament.objects.get(id=id)
        else:
            event = Event.objects.get(slug=slug)
            tournament = Tournament.objects.get(event=event)
    except (Tournament.DoesNotExist, Event.DoesNotExist):
        return 400, {"message": "Tournament does not exist"}

    return 200, tournament


# Tournaments - Roster ##########


@api.get(
    "/tournament/{tournament_slug}/team/{team_slug}/players/search",
    response={200: list[PlayerTinySchema], 400: Response},
)
@paginate(PageNumberPagination, page_size=5)
def event_roster_player_search(
    request: AuthenticatedHttpRequest, tournament_slug: str, team_slug: str, text: str = ""
) -> list[Player] | QuerySet[Player]:
    try:
        event = Event.objects.get(slug=tournament_slug)
    except Event.DoesNotExist:
        return []

    try:
        team = Team.objects.get(slug=team_slug)
    except Team.DoesNotExist:
        return []

    text = text.strip().lower()

    if not event.series:
        return (
            Player.objects.annotate(
                full_name=Concat("user__first_name", Value(" "), "user__last_name")
            )
            .filter(Q(full_name__icontains=text) | Q(user__username__icontains=text))
            .order_by("full_name")
        )

    # Players have to be in the series roster first, to be added to the event roster
    # Membership active status already checked before adding to the season roster
    series_roster_player_ids = SeriesRegistration.objects.filter(
        series=event.series, team=team
    ).values_list("player__id", flat=True)

    return (
        Player.objects.filter(id__in=series_roster_player_ids)
        .annotate(full_name=Concat("user__first_name", Value(" "), "user__last_name"))
        .filter(Q(full_name__icontains=text) | Q(user__username__icontains=text))
        .order_by("full_name")
    )


@api.post(
    "/tournament/{event_id}/team/{team_id}/roster",
    response={200: TournamentPlayerRegistrationSchema, 400: Response, 401: Response},
)
def add_player_to_roster(
    request: AuthenticatedHttpRequest,
    event_id: int,
    team_id: int,
    registration_details: AddToRosterSchema,
) -> tuple[int, Registration] | tuple[int, message_response]:
    try:
        team = Team.objects.get(id=team_id)
        event = Event.objects.get(id=event_id)
        tournament = Tournament.objects.get(event=event)
    except (Event.DoesNotExist, Team.DoesNotExist, Tournament.DoesNotExist):
        return 400, {"message": "Team/Event/Tournament does not exist"}

    if not is_today_in_between_dates(
        from_date=tournament.event.player_registration_start_date,
        to_date=tournament.event.player_registration_end_date,
    ):
        return 400, {"message": "Rostering has closed, you can't roster players now !"}

    if team not in tournament.teams.all():
        return 400, {"message": f"{team.name} is not registered for ${event.title} !"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can roster players to the team"}

    try:
        player = Player.objects.get(id=registration_details.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    if (
        registration_details.role is not None
        and registration_details.role not in Registration.Role._value2member_map_
    ):
        return 400, {"message": "Invalid role"}

    if event.series:
        can_register, error = can_register_player_to_series_event(
            event=event, team=team, player=player
        )
        if not can_register and error:
            return 400, error

    registration = Registration(
        event=event,
        team=team,
        player=player,
    )
    if registration_details.is_playing:
        registration.is_playing = registration_details.is_playing
    if registration_details.role:
        registration.role = registration_details.role
    try:
        registration.save()
    except IntegrityError:
        return 400, {"message": "Player already added to another team for this event"}

    return 200, registration


@api.delete(
    "/tournament/{event_id}/team/{team_id}/roster/{registration_id}",
    response={200: Response, 400: Response, 401: Response},
)
def remove_from_roster(
    request: AuthenticatedHttpRequest,
    event_id: int,
    team_id: int,
    registration_id: int,
) -> tuple[int, message_response]:
    try:
        event = Event.objects.get(id=event_id)
        team = Team.objects.get(id=team_id)
        tournament = Tournament.objects.get(event=event)
    except (Event.DoesNotExist, Team.DoesNotExist, Tournament.DoesNotExist):
        return 400, {"message": "Team/Event/Tournament does not exist"}

    if not is_today_in_between_dates(
        from_date=tournament.event.player_registration_start_date,
        to_date=tournament.event.player_registration_end_date,
    ):
        return 400, {"message": "Rostering has closed, you can't remove players now !"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can remove players from the roster"}

    try:
        registration = Registration.objects.get(id=registration_id, event=event, team=team)
        registration.delete()
        return 200, {"message": "Player registration removed successfully"}

    except Registration.DoesNotExist:
        return 400, {"message": "Registration does not exist"}


@api.put(
    "/tournament/{event_id}/team/{team_id}/roster/{registration_id}",
    response={200: TournamentPlayerRegistrationSchema, 400: Response, 401: Response},
)
def update_registration(
    request: AuthenticatedHttpRequest,
    event_id: int,
    team_id: int,
    registration_id: int,
    registration_details: TournamentPlayerRegistrationUpdateSchema,
) -> tuple[int, Registration] | tuple[int, message_response]:
    try:
        event = Event.objects.get(id=event_id)
        team = Team.objects.get(id=team_id)
        tournament = Tournament.objects.get(event=event)
    except (Event.DoesNotExist, Team.DoesNotExist, Tournament.DoesNotExist):
        return 400, {"message": "Team/Event/Tournament does not exist"}

    if not is_today_in_between_dates(
        from_date=tournament.event.player_registration_start_date,
        to_date=tournament.event.player_registration_end_date,
    ):
        return 400, {"message": "Rostering has closed, you can't edit registrations now !"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can remove players from the roster"}

    try:
        registration = Registration.objects.get(id=registration_id, event=event, team=team)
    except Registration.DoesNotExist:
        return 400, {"message": "Registration does not exist"}

    if registration_details.is_playing is not None:
        registration.is_playing = registration_details.is_playing

    if registration_details.role:
        if registration_details.role not in Registration.Role._value2member_map_:
            return 400, {"message": "Invalid role"}
        registration.role = registration_details.role

    registration.save()
    return 200, registration


@api.get(
    "/v1/tournament/{tournament_slug}/team/{team_slug}/roster",
    auth=None,
    response={200: list[UCRegistrationSchema], 400: Response},
)
def get_tournament_team_roster(
    request: AuthenticatedHttpRequest, tournament_slug: str, team_slug: str
) -> tuple[int, QuerySet[UCRegistration] | message_response]:
    try:
        event = Event.objects.get(slug=tournament_slug)
        team = Team.objects.get(slug=team_slug)

    except (Event.DoesNotExist, Team.DoesNotExist):
        return 400, {"message": "Tournament/Team does not exist"}

    uc_registrations = UCRegistration.objects.filter(team=team, event=event).order_by(
        "person__first_name"
    )

    return 200, uc_registrations


@api.get(
    "/v2/tournament/{tournament_slug}/team/{team_slug}/roster",
    auth=None,
    response={200: list[TournamentPlayerRegistrationSchema], 400: Response},
)
def get_tournament_team_roster_new(
    request: AuthenticatedHttpRequest, tournament_slug: str, team_slug: str
) -> tuple[int, QuerySet[Registration]] | tuple[int, message_response]:
    try:
        event = Event.objects.get(slug=tournament_slug)
        team = Team.objects.get(slug=team_slug)
    except (Event.DoesNotExist, Team.DoesNotExist):
        return 400, {"message": "Tournament/Team does not exist"}

    registrations = Registration.objects.filter(event=event, team=team).order_by(
        "player__user__first_name"
    )

    return 200, registrations


######## Fields


@api.get(
    "/tournament/{tournament_id}/fields",
    auth=None,
    response={200: list[TournamentFieldSchema], 400: Response},
)
def get_fields_by_tournament_id(
    request: AuthenticatedHttpRequest, tournament_id: int
) -> tuple[int, QuerySet[TournamentField] | message_response]:
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    return 200, TournamentField.objects.filter(tournament=tournament).order_by("name")


@api.get(
    "/tournament/slug/{slug}/fields",
    auth=None,
    response={200: list[TournamentFieldSchema], 400: Response},
)
def get_fields_by_tournament_slug(
    request: AuthenticatedHttpRequest, slug: str
) -> tuple[int, QuerySet[TournamentField] | message_response]:
    try:
        event = Event.objects.get(slug=slug)
        tournament = Tournament.objects.get(event=event)
    except Event.DoesNotExist:
        return 400, {"message": "Event does not exist"}
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    return 200, TournamentField.objects.filter(tournament=tournament).order_by("name")


@api.post(
    "/tournament/{tournament_id}/field",
    response={200: TournamentFieldSchema, 400: Response, 401: Response},
)
def create_field(
    request: AuthenticatedHttpRequest,
    tournament_id: int,
    field_details: TournamentFieldCreateSchema,
) -> tuple[int, TournamentField | message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create fields"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    field = TournamentField(
        name=field_details.name.strip(),
        address=field_details.address,
        is_broadcasted=field_details.is_broadcasted,
        tournament=tournament,
    )

    try:
        field.full_clean()

    except ValidationError as e:
        return 400, {"message": str(e)}

    field.save()

    return 200, field


@api.put(
    "/tournament/field/{field_id}",
    response={200: TournamentFieldSchema, 400: Response, 401: Response, 409: Response},
)
def update_field(
    request: AuthenticatedHttpRequest, field_id: int, field_details: TournamentFieldUpdateSchema
) -> tuple[int, TournamentField | message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can edit fields"}

    try:
        tournament = Tournament.objects.get(id=field_details.tournament_id)
        field = TournamentField.objects.get(id=field_id, tournament=tournament)

    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    except TournamentField.DoesNotExist:
        return 400, {"message": "Field does not exist"}

    if field_details.name:
        field.name = field_details.name

    if field_details.is_broadcasted is not None:
        field.is_broadcasted = field_details.is_broadcasted

    if field_details.address:
        field.address = field_details.address

    try:
        field.full_clean()
    except ValidationError as e:
        return 400, {"message": str(e)}

    field.save()

    return 200, field


@api.get(
    "/tournament/slug/{slug}/matches", auth=None, response={200: list[MatchSchema], 400: Response}
)
def get_tournament_matches_by_slug(
    request: AuthenticatedHttpRequest, slug: str
) -> tuple[int, QuerySet[Match] | message_response]:
    try:
        event = Event.objects.get(slug=slug)
        tournament = Tournament.objects.get(event=event)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}
    except Event.DoesNotExist:
        return 400, {"message": "Event does not exist"}

    return 200, Match.objects.filter(tournament=tournament).order_by("time")


@api.get(
    "/tournament/{tournament_slug}/team/{team_slug}/matches",
    auth=None,
    response={200: list[MatchSchema], 400: Response},
)
def get_tournament_team_matches(
    request: AuthenticatedHttpRequest, tournament_slug: str, team_slug: str
) -> tuple[int, QuerySet[Match] | message_response]:
    try:
        event = Event.objects.get(slug=tournament_slug)
        tournament = Tournament.objects.get(event=event)
        team = Team.objects.get(slug=team_slug)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}
    except Event.DoesNotExist:
        return 400, {"message": "Event does not exist"}
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    tournament_team_matches = Match.objects.filter(
        Q(team_1=team) | Q(team_2=team), tournament=tournament
    ).order_by("time")

    return 200, tournament_team_matches


@api.post("/tournaments", response={200: TournamentSchema, 400: Response, 401: Response})
def create_tournament(
    request: AuthenticatedHttpRequest,
    tournament_details: TournamentCreateSchema,
    logo_light: UploadedFile | None = File(None),  # noqa: B008
    logo_dark: UploadedFile | None = File(None),  # noqa: B008
) -> tuple[int, Tournament] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create tournament"}

    datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
    if if_dates_are_not_in_order(tournament_details.start_date, tournament_details.end_date):
        return 400, {"message": "Start date can't be after end date"}

    if if_dates_are_not_in_order(
        tournament_details.team_registration_start_date,
        tournament_details.team_registration_end_date,
    ):
        return 400, {
            "message": "Team Registration Start date can't be after Team Registration end date"
        }

    if if_dates_are_not_in_order(
        tournament_details.team_registration_end_date, tournament_details.start_date
    ):
        return 400, {"message": "Registration End date can't be after Tournament Start date"}

    if if_dates_are_not_in_order(
        tournament_details.player_registration_start_date,
        tournament_details.player_registration_end_date,
    ):
        return 400, {
            "message": "Player Registration Start date can't be after Player Registration End date"
        }

    if if_dates_are_not_in_order(
        tournament_details.team_registration_start_date,
        tournament_details.player_registration_start_date,
    ):
        return 400, {"message": "Player registration can't start before Team registration starts"}

    if if_dates_are_not_in_order(
        tournament_details.team_registration_end_date,
        tournament_details.player_registration_end_date,
    ):
        return 400, {"message": "Player registration can't end before Team registration ends"}

    event = Event(
        title=tournament_details.title,
        start_date=tournament_details.start_date,
        end_date=tournament_details.end_date,
        team_registration_start_date=tournament_details.team_registration_start_date,
        team_registration_end_date=tournament_details.team_registration_end_date,
        player_registration_start_date=tournament_details.player_registration_start_date,
        player_registration_end_date=tournament_details.player_registration_end_date,
        location=tournament_details.location,
        type=tournament_details.type,
    )
    event.save()

    tournament = Tournament(event=event)

    if logo_light:
        tournament.logo_light = logo_light
    if logo_dark:
        tournament.logo_dark = logo_dark

    tournament.rules = get_default_rules()

    if if_today(tournament_details.team_registration_start_date):
        tournament.status = Tournament.Status.REGISTERING

    tournament.save()

    return 200, tournament


@api.post("/tournaments/event", response={200: TournamentSchema, 400: Response, 401: Response})
def create_tournament_from_event(
    request: AuthenticatedHttpRequest,
    tournament_details: TournamentCreateFromEventSchema,
    logo_light: UploadedFile | None = File(None),  # noqa: B008
    logo_dark: UploadedFile | None = File(None),  # noqa: B008
) -> tuple[int, Tournament] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create tournament"}

    try:
        event = Event.objects.get(id=tournament_details.event_id)
    except Event.DoesNotExist:
        return 400, {"message": "Event does not exist"}

    tournament, created = Tournament.objects.get_or_create(event=event)

    if not created:
        return 400, {"message": "Tournament already exists"}

    team_list = UCRegistration.objects.filter(event=event).values_list("team", flat=True).distinct()
    for team_id in team_list:
        tournament.teams.add(team_id)

    if logo_light:
        tournament.logo_light = logo_light
    if logo_dark:
        tournament.logo_dark = logo_dark

    tournament.rules = get_default_rules()
    tournament.use_uc_registrations = True

    tournament.save()

    return 200, tournament


@api.put(
    "/tournament/{tournament_id}/register-team",
    response={200: TournamentSchema, 400: Response, 401: Response},
)
def add_team_registration(
    request: AuthenticatedHttpRequest,
    tournament_id: int,
    team_details: AddOrRemoveTeamRegistrationSchema,
) -> tuple[int, Tournament] | tuple[int, message_response]:
    try:
        team = Team.objects.get(id=team_details.team_id)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can register a team to a tournament !"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    if tournament.status != Tournament.Status.REGISTERING:
        return 400, {"message": "Team registration has closed, you can't register a team now !"}

    if tournament.event.series and team not in tournament.event.series.teams.all():
        return 400, {
            "message": "Team is not part of the series",
            "description": f"Your team has to be registered for the {tournament.event.series.name} series, to participate in this tournament.",
            "action_name": "Register",
            "action_href": f"/series/{tournament.event.series.slug}/",
        }

    if tournament.event.team_fee > 0:
        return 400, {"message": "Team registration can be done only after payment of team fee !"}

    tournament.teams.add(team)

    return 200, tournament


@api.put(
    "/tournament/{tournament_id}/deregister-team",
    response={200: TournamentSchema, 400: Response, 401: Response},
)
def remove_team_registration(
    request: AuthenticatedHttpRequest,
    tournament_id: int,
    team_details: AddOrRemoveTeamRegistrationSchema,
) -> tuple[int, Tournament] | tuple[int, message_response]:
    try:
        team = Team.objects.get(id=team_details.team_id)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can de-register a team from a tournament !"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    if tournament.status != Tournament.Status.REGISTERING:
        return 400, {"message": "Team registration has closed, you can't de-register a team now !"}

    tournament.teams.remove(team)

    return 200, tournament


@api.put(
    "/tournament/update/{tournament_id}",
    response={200: TournamentSchema, 400: Response, 401: Response},
)
def update_standings(
    request: AuthenticatedHttpRequest,
    tournament_id: int,
    tournament_details: TournamentUpdateSeedingSchema,
) -> tuple[int, Tournament] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can update tournament"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    valid_seeds_and_teams, errors = validate_seeds_and_teams(tournament, tournament_details.seeding)

    if not valid_seeds_and_teams:
        message = "Cannot update standings, due to following errors: \n"
        message += "\n".join(f"{key}: {value}" for key, value in errors.items())
        return 400, {"message": message}

    tournament.initial_seeding = dict(sorted(tournament_details.seeding.items()))
    tournament.current_seeding = dict(sorted(tournament_details.seeding.items()))
    tournament.save()

    return 200, tournament


@api.delete(
    "/tournament/delete/{tournament_id}", response={200: Response, 400: Response, 401: Response}
)
def delete_tournament(
    request: AuthenticatedHttpRequest, tournament_id: int
) -> tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can delete tournament"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    tournament.delete()

    return 200, {"message": "Tournament successfully deleted"}


@api.post(
    "/tournament/pool/{tournament_id}", response={200: PoolSchema, 400: Response, 401: Response}
)
def create_pool(
    request: AuthenticatedHttpRequest, tournament_id: int, pool_details: PoolCreateSchema
) -> tuple[int, Pool] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create pools"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    valid_pool, errors = validate_new_pool(
        tournament=tournament, new_pool=set(pool_details.seeding)
    )
    if not valid_pool:
        message = "Cannot create pools, due to following errors: \n"
        message += "\n".join(f"{key}: {value}" for key, value in errors.items())
        return 400, {"message": message}

    # seed -> team_id. If the same seed present twice, we'll only get one object since its a map with seed as the key
    pool_seeding: dict[int, str] = {}
    pool_results: dict[str, Any] = {}
    for i, seed in enumerate(pool_details.seeding):
        team_id = tournament.initial_seeding[str(seed)]

        pool_seeding[seed] = team_id
        pool_results[team_id] = {
            "rank": i + 1,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "GF": 0,  # Goals For
            "GA": 0,  # Goals Against
        }

    pool = Pool(
        sequence_number=pool_details.sequence_number,
        name=pool_details.name,
        tournament=tournament,
        initial_seeding=dict(sorted(pool_seeding.items())),
        results=pool_results,
    )
    pool.save()

    create_pool_matches(tournament, pool)

    return 200, pool


@api.get("/tournament/pools", auth=None, response={200: list[PoolSchema], 400: Response})
def get_pools(
    request: AuthenticatedHttpRequest, id: int = 0, slug: str = ""
) -> tuple[int, QuerySet[Pool]] | tuple[int, message_response]:
    if id == 0 and slug == "":
        return 400, {"message": "Need either tournament id or slug"}
    try:
        if id != 0:
            tournament = Tournament.objects.get(id=id)
        else:
            event = Event.objects.get(slug=slug)
            tournament = Tournament.objects.get(event=event)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    return 200, Pool.objects.filter(tournament=tournament).order_by("name")


@api.post(
    "/tournament/cross-pool/{tournament_id}",
    response={200: CrossPoolSchema, 400: Response, 401: Response},
)
def create_cross_pool(
    request: AuthenticatedHttpRequest, tournament_id: int
) -> tuple[int, CrossPool] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create pools"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    cross_pool = CrossPool(tournament=tournament)
    cross_pool.save()

    return 200, cross_pool


@api.get("/tournament/cross-pool", auth=None, response={200: CrossPoolSchema, 400: Response})
def get_cross_pool(
    request: AuthenticatedHttpRequest, id: int | None = None, slug: str | None = None
) -> tuple[int, CrossPool] | tuple[int, message_response]:
    if id is None and slug is None:
        return 400, {"message": "Need either tournament id or slug"}
    try:
        if id is not None:
            tournament = Tournament.objects.get(id=id)
        else:
            event = Event.objects.get(slug=slug)
            tournament = Tournament.objects.get(event=event)
        cross_pool = CrossPool.objects.get(tournament=tournament)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}
    except CrossPool.DoesNotExist:
        return 400, {"message": "Cross Pool does not exist"}

    return 200, cross_pool


@api.post(
    "/tournament/bracket/{tournament_id}",
    response={200: BracketSchema, 400: Response, 401: Response},
)
def create_bracket(
    request: AuthenticatedHttpRequest, tournament_id: int, bracket_details: BracketCreateSchema
) -> tuple[int, Bracket] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create brackets"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    bracket_seeding = {}
    start, end = map(int, bracket_details.name.split("-"))
    for i in range(start, end + 1):
        bracket_seeding[i] = 0

    bracket = Bracket(
        sequence_number=bracket_details.sequence_number,
        name=bracket_details.name,
        tournament=tournament,
        initial_seeding=dict(sorted(bracket_seeding.items())),
        current_seeding=dict(sorted(bracket_seeding.items())),
    )
    bracket.save()

    create_bracket_matches(tournament, bracket)

    return 200, bracket


@api.get("/tournament/brackets", auth=None, response={200: list[BracketSchema], 400: Response})
def get_brackets(
    request: AuthenticatedHttpRequest, id: int | None = None, slug: str | None = None
) -> tuple[int, QuerySet[Bracket]] | tuple[int, message_response]:
    if id is None and slug is None:
        return 400, {"message": "Need either tournament id or slug"}
    try:
        if id is not None:
            tournament = Tournament.objects.get(id=id)
        else:
            event = Event.objects.get(slug=slug)
            tournament = Tournament.objects.get(event=event)
    except (Tournament.DoesNotExist, Event.DoesNotExist):
        return 400, {"message": "Tournament does not exist"}

    return 200, Bracket.objects.filter(tournament=tournament)


@api.post(
    "/tournament/position-pool/{tournament_id}",
    response={200: PositionPoolSchema, 400: Response, 401: Response},
)
def create_position_pool(
    request: AuthenticatedHttpRequest,
    tournament_id: int,
    position_pool_details: PositionPoolCreateSchema,
) -> tuple[int, PositionPool] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create position pools"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    pool_seeding = {}
    for seed in position_pool_details.seeding:
        pool_seeding[seed] = 0

    pool = PositionPool(
        sequence_number=position_pool_details.sequence_number,
        name=position_pool_details.name,
        tournament=tournament,
        initial_seeding=dict(sorted(pool_seeding.items())),
        results={},
    )
    pool.save()

    create_position_pool_matches(tournament, pool)

    return 200, pool


@api.get(
    "/tournament/position-pools",
    auth=None,
    response={200: list[PositionPoolSchema], 400: Response},
)
def get_position_pools(
    request: AuthenticatedHttpRequest, id: int | None = None, slug: str | None = None
) -> tuple[int, QuerySet[PositionPool]] | tuple[int, message_response]:
    if id is None and slug is None:
        return 400, {"message": "Need either tournament id or slug"}
    try:
        if id is not None:
            tournament = Tournament.objects.get(id=id)
        else:
            event = Event.objects.get(slug=slug)
            tournament = Tournament.objects.get(event=event)
    except (Tournament.DoesNotExist, Event.DoesNotExist):
        return 400, {"message": "Tournament does not exist"}

    return 200, PositionPool.objects.filter(tournament=tournament)


@api.post(
    "/tournament/match/{tournament_id}", response={200: MatchSchema, 400: Response, 401: Response}
)
def create_match(
    request: AuthenticatedHttpRequest, tournament_id: int, match_details: MatchCreateSchema
) -> tuple[int, Match] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create matches"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    ind_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
    match_datetime = datetime.datetime.strptime(match_details.time, "%Y-%m-%dT%H:%M").astimezone(
        ind_tz
    )

    try:
        field = TournamentField.objects.get(id=match_details.field_id, tournament=tournament)
    except TournamentField.DoesNotExist:
        return 400, {"message": "Field does not exist"}

    match = Match(
        tournament=tournament,
        sequence_number=match_details.seq_num,
        time=match_datetime,
        field=field,
        placeholder_seed_1=match_details.seed_1,
        placeholder_seed_2=match_details.seed_2,
    )

    try:
        seed_1 = min(match_details.seed_1, match_details.seed_2)
        seed_2 = max(match_details.seed_1, match_details.seed_2)

        if match_details.stage == "pool":
            pool = Pool.objects.get(id=match_details.stage_id)
            match.pool = pool
            match.name = f"{pool.name}{seed_1} v {pool.name}{seed_2}"

        elif match_details.stage == "bracket":
            bracket = Bracket.objects.get(id=match_details.stage_id)
            match.bracket = bracket
            seeds = sorted(map(int, bracket.initial_seeding.keys()))
            start, end = seeds[0], seeds[-1]
            match.name = get_bracket_match_name(start=start, end=end, seed_1=seed_1, seed_2=seed_2)

        elif match_details.stage == "cross_pool":
            cross_pool = CrossPool.objects.get(id=match_details.stage_id)
            match.cross_pool = cross_pool
            match.name = "Cross Pool"

        elif match_details.stage == "position_pool":
            position_pool = PositionPool.objects.get(id=match_details.stage_id)
            match.position_pool = position_pool
            match.name = f"{position_pool.name}{seed_1} v {position_pool.name}{seed_2}"

    except (
        Pool.DoesNotExist,
        Bracket.DoesNotExist,
        CrossPool.DoesNotExist,
        PositionPool.DoesNotExist,
    ):
        return 400, {"message": "Stage does not exist"}

    match.save()

    return 200, match


@api.get(
    "/tournament/{tournament_id}/matches",
    auth=None,
    response={200: list[MatchSchema], 400: Response},
)
def get_matches(
    request: AuthenticatedHttpRequest, tournament_id: int
) -> tuple[int, QuerySet[Match]] | tuple[int, message_response]:
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    return 200, Match.objects.filter(tournament=tournament).order_by("time")


@api.post(
    "/tournament/start/{tournament_id}",
    response={200: TournamentSchema, 400: Response, 401: Response},
)
def start_tournament(
    request: AuthenticatedHttpRequest, tournament_id: int
) -> tuple[int, Tournament] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can start tournament"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    pool_matches = Match.objects.filter(tournament=tournament).exclude(pool__isnull=True)

    for match in pool_matches:
        team_1_id = tournament.initial_seeding[str(match.placeholder_seed_1)]
        team_2_id = tournament.initial_seeding[str(match.placeholder_seed_2)]

        team_1 = Team.objects.get(id=team_1_id)
        team_2 = Team.objects.get(id=team_2_id)

        match.team_1 = team_1
        match.team_2 = team_2
        match.status = Match.Status.SCHEDULED

        match.save()

    tournament.status = Tournament.Status.LIVE
    tournament.save()

    return 200, tournament


@api.post(
    "/tournament/generate-fixtures/{tournament_id}",
    response={200: Response, 400: Response, 401: Response},
)
def generate_tournament_fixtures(
    request: AuthenticatedHttpRequest, tournament_id: int
) -> tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can start tournament"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    populate_fixtures(tournament.id)

    return 200, {"message": "Tournament fixtures populated"}


@api.post(
    "/tournament/rules/{tournament_id}",
    response={200: TournamentSchema, 400: Response, 401: Response},
)
def update_rules(
    request: AuthenticatedHttpRequest, tournament_id: int, tournament_rules: TournamentRulesSchema
) -> tuple[int, Tournament | message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can edit rules"}

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    tournament.rules = tournament_rules.rules
    tournament.save()

    return 200, tournament


@api.get("/match/{match_id}", auth=None, response={200: MatchSchema, 400: Response})
def get_match(request: HttpRequest, match_id: int) -> tuple[int, Match | message_response]:
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return 400, {"message": "Match does not exist"}

    return 200, match


@api.post("/match/{match_id}/score", response={200: MatchSchema, 400: Response, 401: Response})
def add_match_score(
    request: AuthenticatedHttpRequest, match_id: int, match_scores: MatchScoreSchema
) -> tuple[int, Match | message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can add scores"}

    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return 400, {"message": "Match does not exist"}

    if match.status in {Match.Status.COMPLETED, Match.Status.YET_TO_FIX}:
        return 400, {"message": "Match score cant be added in current status"}

    update_match_score_and_results(match, match_scores.team_1_score, match_scores.team_2_score)
    populate_fixtures(match.tournament.id)

    return 200, match


@api.post(
    "/match/{match_id}/submit-score", response={200: MatchSchema, 400: Response, 401: Response}
)
def submit_match_score(
    request: AuthenticatedHttpRequest, match_id: int, match_scores: MatchScoreSchema
) -> tuple[int, Match | message_response]:
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return 400, {"message": "Match does not exist"}

    if (
        match.status in {Match.Status.COMPLETED, Match.Status.YET_TO_FIX}
        or match.team_1 is None
        or match.team_2 is None
    ):
        return 400, {"message": "Match score cant be submitted in current status"}

    player_team_id, admin_team_ids = user_tournament_teams(match.tournament, request.user)

    if match.team_1.id not in admin_team_ids and match.team_2.id not in admin_team_ids:
        return 401, {"message": "User not authorised to add score for this match"}

    match_score = MatchScore.objects.create(
        score_team_1=match_scores.team_1_score,
        score_team_2=match_scores.team_2_score,
        entered_by=request.user.player_profile,
    )

    if match.team_1.id in admin_team_ids:
        match.suggested_score_team_1 = match_score
    if match.team_2.id in admin_team_ids:
        match.suggested_score_team_2 = match_score

    match.save()
    match.refresh_from_db()

    if is_submitted_scores_equal(match):
        update_match_score_and_results(match, match_scores.team_1_score, match_scores.team_2_score)
        populate_fixtures(match.tournament.id)

    return 200, match


@api.post("/match/{match_id}/update", response={200: MatchSchema, 400: Response, 401: Response})
def update_match(
    request: AuthenticatedHttpRequest, match_id: int, match_details: MatchUpdateSchema
) -> tuple[int, Match] | tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can update matches"}

    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return 400, {"message": "Match does not exist"}

    if match_details.time:
        ind_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
        match_datetime = datetime.datetime.strptime(
            match_details.time, "%Y-%m-%dT%H:%M"
        ).astimezone(ind_tz)

        match.time = match_datetime

    if match_details.field_id:
        try:
            field = TournamentField.objects.get(
                id=match_details.field_id, tournament=match.tournament
            )
        except TournamentField.DoesNotExist:
            return 400, {"message": "Field does not exist"}

        match.field = field

    use_uc_reg = match.tournament.use_uc_registrations

    if match_details.video_url:
        match.video_url = match_details.video_url

    if match_details.duration_mins:
        match.duration_mins = match_details.duration_mins

    if match_details.spirit_score_team_1:
        match.spirit_score_team_1 = create_spirit_scores(
            match_details.spirit_score_team_1, use_uc_reg
        )

    if match_details.spirit_score_team_2:
        match.spirit_score_team_2 = create_spirit_scores(
            match_details.spirit_score_team_2, use_uc_reg
        )

    if match_details.self_spirit_score_team_1:
        match.self_spirit_score_team_1 = create_spirit_scores(
            match_details.self_spirit_score_team_1, use_uc_reg
        )

    if match_details.self_spirit_score_team_2:
        match.self_spirit_score_team_2 = create_spirit_scores(
            match_details.self_spirit_score_team_2, use_uc_reg
        )

    match.save()

    if (
        match_details.spirit_score_team_1
        or match_details.spirit_score_team_2
        or match_details.self_spirit_score_team_1
        or match_details.self_spirit_score_team_2
    ):
        update_tournament_spirit_rankings(match.tournament)

    return 200, match


@api.post(
    "/match/{match_id}/submit-spirit-score",
    response={200: MatchSchema, 400: Response, 401: Response},
)
def submit_match_spirit_score(
    request: AuthenticatedHttpRequest, match_id: int, spirit_score: SpiritScoreSubmitSchema
) -> tuple[int, Match] | tuple[int, message_response]:
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return 400, {"message": "Match does not exist"}

    player_team_id, admin_team_ids = user_tournament_teams(match.tournament, request.user)

    if spirit_score.team_id not in admin_team_ids:
        return 401, {"message": "User not authorised to add score for this match"}

    use_uc_reg = match.tournament.use_uc_registrations

    if match.team_1 is not None and match.team_1.id == spirit_score.team_id:
        match.spirit_score_team_2 = create_spirit_scores(spirit_score.opponent, use_uc_reg)
        match.self_spirit_score_team_1 = create_spirit_scores(spirit_score.self, use_uc_reg)
    elif match.team_2 is not None and match.team_2.id == spirit_score.team_id:
        match.spirit_score_team_1 = create_spirit_scores(spirit_score.opponent, use_uc_reg)
        match.self_spirit_score_team_2 = create_spirit_scores(spirit_score.self, use_uc_reg)
    else:
        return 401, {"message": "User not authorised to add score for this match"}

    match.save()
    update_tournament_spirit_rankings(match.tournament)
    return 200, match


@api.delete("/match/{match_id}", response={200: Response, 400: Response, 401: Response})
def delete_match(request: AuthenticatedHttpRequest, match_id: int) -> tuple[int, message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can delete matches"}

    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return 400, {"message": "Match does not exist"}

    match.delete()

    return 200, {"message": "Success"}


# Match Stats ##########


@api.post("/match/{match_id}/stats", response={200: MatchStatsSchema, 400: Response, 401: Response})
def create_match_stats(
    request: AuthenticatedHttpRequest, match_id: int, body: MatchStatsCreateSchema
) -> tuple[int, MatchStats | message_response]:
    try:
        match = Match.objects.get(id=match_id)
        team = Team.objects.get(id=body.initial_possession_team_id)
    except (Match.DoesNotExist, Team.DoesNotExist):
        return 400, {"message": "Match or Team does not exist"}

    if request.user not in match.tournament.volunteers.all():
        return 401, {"message": "Only Tournament volunteers can create match stats"}

    if match.status in {Match.Status.YET_TO_FIX} or match.team_1 is None or match.team_2 is None:
        return 400, {"message": "Match stats cant be created in current status"}

    match_stats = MatchStats.objects.create(
        match=match, tournament=match.tournament, initial_possession=team, current_possession=team
    )

    # NOTE: ignoring line selection for regionals stats
    match_stats.status_team_1 = MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
    match_stats.status_team_2 = MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
    match_stats.save()

    return 200, match_stats


@api.get("/match/{match_id}/stats", auth=None, response={200: MatchStatsSchema, 400: Response})
def get_match_stats(
    request: HttpRequest, match_id: int
) -> tuple[int, MatchStats | message_response]:
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return 400, {"message": "Match does not exist"}

    try:
        stats = MatchStats.objects.get(match=match)
    except MatchStats.DoesNotExist:
        return 400, {"message": "Stats does not exist"}

    return 200, stats


@api.post(
    "/match/{match_id}/stats/event",
    response={200: MatchStatsSchema, 400: Response, 401: Response, 422: Response},
)
def create_match_stats_event(
    request: AuthenticatedHttpRequest, match_id: int, body: MatchEventCreateSchema
) -> tuple[int, MatchStats | message_response]:
    try:
        match = Match.objects.get(id=match_id)
        MatchStats.objects.get(match=match)
        team = Team.objects.get(id=body.team_id)
    except (Match.DoesNotExist, MatchStats.DoesNotExist, Team.DoesNotExist):
        return 400, {"message": "Match or Stats or Team does not exist"}

    if request.user not in match.tournament.volunteers.all():
        return 401, {"message": "Only Tournament volunteers can create match stats"}

    return handle_all_events(match_event=body, match=match, team=team)


@api.post(
    "/match/{match_id}/stats/switch-offense",
    response={200: MatchStatsSchema, 400: Response, 401: Response, 422: Response},
)
def switch_offense(
    request: AuthenticatedHttpRequest, match_id: int
) -> tuple[int, MatchStats | message_response]:
    try:
        match = Match.objects.get(id=match_id)
        MatchStats.objects.get(match=match)
    except (Match.DoesNotExist, MatchStats.DoesNotExist):
        return 400, {"message": "Match or Stats does not exist"}

    if request.user not in match.tournament.volunteers.all():
        return 401, {"message": "Only Tournament volunteers can update match stats"}

    return handle_switch_offense(match=match)


@api.post(
    "/match/{match_id}/stats/event/undo",
    response={200: MatchStatsSchema, 400: Response, 401: Response, 422: Response},
)
def match_stats_undo(
    request: AuthenticatedHttpRequest, match_id: int
) -> tuple[int, MatchStats | message_response]:
    try:
        match = Match.objects.get(id=match_id)
        MatchStats.objects.get(match=match)
    except (Match.DoesNotExist, MatchStats.DoesNotExist):
        return 400, {"message": "Match or Team does not exist"}

    if request.user not in match.tournament.volunteers.all():
        return 401, {"message": "Only Tournament volunteers can update match stats"}

    return handle_undo(match)


@api.post(
    "/match/{match_id}/stats/half-time",
    response={200: MatchStatsSchema, 400: Response, 401: Response, 422: Response},
)
def match_stats_half_time(
    request: AuthenticatedHttpRequest, match_id: int
) -> tuple[int, MatchStats | message_response]:
    try:
        match = Match.objects.get(id=match_id)
        MatchStats.objects.get(match=match)
    except (Match.DoesNotExist, MatchStats.DoesNotExist):
        return 400, {"message": "Match or Team does not exist"}

    if request.user not in match.tournament.volunteers.all():
        return 401, {"message": "Only Tournament volunteers can update match stats"}

    return handle_half_time(match)


@api.post(
    "/match/{match_id}/stats/full-time",
    response={200: MatchStatsSchema, 400: Response, 401: Response, 422: Response},
)
def match_stats_full_time(
    request: AuthenticatedHttpRequest, match_id: int
) -> tuple[int, MatchStats | message_response]:
    try:
        match = Match.objects.get(id=match_id)
        MatchStats.objects.get(match=match)
    except (Match.DoesNotExist, MatchStats.DoesNotExist):
        return 400, {"message": "Match or Team does not exist"}

    if request.user not in match.tournament.volunteers.all():
        return 401, {"message": "Only Tournament volunteers can update match stats"}

    return handle_full_time(match)


@api.get(
    "/tournament/{tournament_slug}/leaderboard",
    auth=None,
    response={200: dict[str, list[dict[str, Any]]], 400: Response},
)
def get_tournament_leaderboard(
    request: AuthenticatedHttpRequest, tournament_slug: str
) -> tuple[int, Any | message_response]:
    try:
        event = Event.objects.get(slug=tournament_slug)
        tournament = Tournament.objects.get(event=event)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}
    except Event.DoesNotExist:
        return 400, {"message": "Event does not exist"}

    match_stats = MatchStats.objects.filter(tournament=tournament).values_list("id", flat=True)

    scores = (
        MatchEvent.objects.filter(stats_id__in=match_stats, type=MatchEvent.EventType.SCORE)
        .annotate(
            first_name=F("scored_by__user__first_name"),
            last_name=F("scored_by__user__last_name"),
            team_name=F("team__name"),
        )
        .values("scored_by_id", "first_name", "last_name", "team_name")
        .annotate(num_scores=Count("scored_by_id"))
        .order_by("-num_scores")
    )

    assists = (
        MatchEvent.objects.filter(stats_id__in=match_stats, type=MatchEvent.EventType.SCORE)
        .annotate(
            first_name=F("assisted_by__user__first_name"),
            last_name=F("assisted_by__user__last_name"),
            team_name=F("team__name"),
        )
        .values("assisted_by_id", "first_name", "last_name", "team_name")
        .annotate(num_assists=Count("assisted_by_id"))
        .order_by("-num_assists")
    )

    return 200, {"scores": list(scores), "assists": list(assists)}


# Contact Form ##########
@api.post("/contact", response={200: Response, 400: Response, 422: Response})
def contact(
    request: AuthenticatedHttpRequest,
    contact_form: ContactFormSchema,
    attachment: UploadedFile | None = File(None),  # noqa: B008
) -> tuple[int, message_response]:
    name = request.user.get_full_name()
    message = f"Name: {name}\nEmail: {request.user.email}\n\n{contact_form.description}"
    if attachment:
        name = f"contact-form-attachments/{attachment.name}"
        path = default_storage.save(name, attachment)  # type: ignore[attr-defined]
        location = f"{settings.MEDIA_URL}{path}"
        url = request.build_absolute_uri(location)
        message += f"\n\nAttachment: {url}"

    try:
        mail.send_mail(
            subject=contact_form.subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.EMAIL_SUPPORT],
            fail_silently=False,
        )
        return 200, {"message": "Email sent successfully."}
    except Exception as e:
        return 422, {"message": str(e)}

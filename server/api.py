import contextlib
import datetime
import enum
import hashlib
import io
import json
import time
from base64 import b32encode, b64decode
from typing import Any, cast

import pyotp
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.base_user import AbstractBaseUser
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models import Model, Q, QuerySet
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

from server.constants import EVENT_MEMBERSHIP_AMOUNT, MEMBERSHIP_END, MEMBERSHIP_START
from server.lib.manual_transactions import validate_manual_transactions
from server.lib.membership import get_membership_status
from server.models import (
    Accreditation,
    Bracket,
    CollegeId,
    CommentaryInfo,
    CrossPool,
    Event,
    Guardianship,
    ManualTransaction,
    Match,
    MatchScore,
    Membership,
    PhonePeTransaction,
    Player,
    Pool,
    PositionPool,
    RazorpayTransaction,
    Registration,
    Team,
    Tournament,
    TournamentField,
    UCPerson,
    UCRegistration,
    User,
    Vaccination,
)
from server.passkey_utils import PassKeyClient
from server.phonepe_utils import (
    check_transaction_status,
    initiate_payment,
    verify_callback_checksum,
)
from server.schema import (
    AccreditationFormSchema,
    AccreditationSchema,
    AddOrRemoveTeamRegistrationSchema,
    AddToRosterSchema,
    AnnualMembershipSchema,
    BracketCreateSchema,
    BracketSchema,
    CollegeIdFormSchema,
    CollegeIdSchema,
    CommentaryInfoFormSchema,
    CommentaryInfoSchema,
    ContactFormSchema,
    Credentials,
    CrossPoolSchema,
    EventMembershipSchema,
    EventSchema,
    GroupMembershipSchema,
    GuardianshipFormSchema,
    ManualTransactionLiteSchema,
    ManualTransactionSchema,
    ManualTransactionValidationFormSchema,
    MatchCreateSchema,
    MatchSchema,
    MatchScoreSchema,
    MatchUpdateSchema,
    NotVaccinatedFormSchema,
    OrderSchema,
    OTPLoginCredentials,
    OTPRequestCredentials,
    OTPRequestResponse,
    PasskeyRequestSchema,
    PasskeyResponseSchema,
    PaymentFormSchema,
    PhonePePaymentSchema,
    PhonePeTransactionSchema,
    PlayerFormSchema,
    PlayerSchema,
    PlayerTinySchema,
    PoolCreateSchema,
    PoolSchema,
    PositionPoolCreateSchema,
    PositionPoolSchema,
    RazorpayTransactionSchema,
    RegistrationGuardianSchema,
    RegistrationOthersSchema,
    RegistrationSchema,
    RegistrationWardSchema,
    RemoveFromRosterSchema,
    Response,
    SpiritScoreSubmitSchema,
    TeamCreateSchema,
    TeamSchema,
    TeamUpdateSchema,
    TopScoreCredentials,
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
    UserAccessSchema,
    UserFormSchema,
    UserMinSchema,
    UserSchema,
    VaccinatedFormSchema,
    VaccinationSchema,
    ValidationStatsSchema,
    WaiverFormSchema,
)
from server.top_score_utils import TopScoreClient
from server.tournament import (
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
from server.types import message_response
from server.utils import (
    RAZORPAY_DESCRIPTION_MAX,
    RAZORPAY_NOTES_MAX,
    create_razorpay_order,
    if_dates_are_not_in_order,
    if_today,
    verify_razorpay_payment,
    verify_razorpay_webhook_payload,
)

api = NinjaAPI(auth=django_auth, csrf=True)


class AuthenticatedHttpRequest(HttpRequest):
    user: User


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
    }


# Users ##########


@api.get("/users/search", response={200: list[UserMinSchema]})
def search_users(request: AuthenticatedHttpRequest, text: str = "") -> QuerySet[User]:
    return User.objects.filter(
        Q(first_name__icontains=text.lower())
        | Q(last_name__icontains=text.lower())
        | Q(username__icontains=text.lower())
    ).order_by("first_name")


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


# Payments ##########


class PaymentGateway(enum.Enum):
    RAZORPAY = "R"
    PHONEPE = "P"
    MANUAL = "M"


@api.post(
    "/manual-transaction/{transaction_id}",
    response={200: ManualTransactionLiteSchema, 400: Response, 422: Response, 502: str},
)
def create_manual_transaction(
    request: AuthenticatedHttpRequest,
    transaction_id: str,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    return create_transaction(request, order, PaymentGateway.MANUAL, transaction_id)


@api.post("/create-order", response={200: OrderSchema, 400: Response, 422: Response, 502: str})
def create_razorpay_transaction(
    request: AuthenticatedHttpRequest,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    return create_transaction(request, order, PaymentGateway.RAZORPAY)


@api.post(
    "/initiate-payment",
    response={200: PhonePePaymentSchema, 400: Response, 422: Response, 502: str},
)
def initiate_phonepe_payment(
    request: AuthenticatedHttpRequest,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    return create_transaction(request, order, PaymentGateway.PHONEPE)


def create_transaction(
    request: AuthenticatedHttpRequest,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
    gateway: PaymentGateway,
    transaction_id: str | None = None,
) -> tuple[int, str | message_response | dict[str, Any]]:
    if isinstance(order, GroupMembershipSchema):
        group_payment = True
        players = Player.objects.filter(id__in=order.player_ids)
        player_ids = {p.id for p in players}
        if len(player_ids) != len(order.player_ids):
            missing_players = set(order.player_ids) - player_ids
            return 422, {
                "message": f"Some players couldn't be found in the DB: {sorted(missing_players)}"
            }

    else:
        group_payment = False
        try:
            player = Player.objects.get(id=order.player_id)
        except Player.DoesNotExist:
            return 422, {"message": "Player does not exist!"}

    if isinstance(order, GroupMembershipSchema | AnnualMembershipSchema):
        start_date = datetime.date(order.year, *MEMBERSHIP_START)
        end_date = datetime.date(order.year + 1, *MEMBERSHIP_END)
        is_annual = True
        event = None
        amount = (
            sum(player.membership_amount for player in players)
            if isinstance(order, GroupMembershipSchema)
            else player.membership_amount
        )

    elif isinstance(order, EventMembershipSchema):
        try:
            event = Event.objects.get(id=order.event_id)
        except Event.DoesNotExist:
            return 422, {"message": "Event does not exist!"}

        start_date = event.start_date
        end_date = event.end_date
        is_annual = False
        amount = EVENT_MEMBERSHIP_AMOUNT

    else:
        # NOTE: We should never be here, thanks to request validation!
        pass

    user = request.user
    ts = round(time.time())
    membership_defaults = {
        "is_annual": is_annual,
        "start_date": start_date,
        "end_date": end_date,
        "event": event,
    }
    if group_payment:
        player_names = ", ".join(sorted([player.user.get_full_name() for player in players]))
        if len(player_names) > RAZORPAY_NOTES_MAX:
            player_names = player_names[:500] + "..."
        notes = {
            "user_id": user.id,
            "player_ids": str(player_ids),
            "players": player_names,
        }
        receipt = f"group:{start_date}:{ts}"
        for player in players:
            Membership.objects.get_or_create(player=player, defaults=membership_defaults)
    else:
        membership, _ = Membership.objects.get_or_create(
            player=player,
            defaults=membership_defaults,
        )
        notes = {
            "user_id": user.id,
            "player_id": player.id,
            "membership_id": membership.id,
        }
        receipt = f"{membership.membership_number}:{start_date}:{ts}"

    if gateway == PaymentGateway.RAZORPAY:
        data = create_razorpay_order(amount, receipt=receipt, notes=notes)
        if data is None:
            return 502, "Failed to connect to Razorpay."
    elif gateway == PaymentGateway.PHONEPE:
        host = f"{request.scheme}://{request.get_host()}"
        next_url = "/membership/group" if group_payment else f"/membership/{player.id}"
        data = initiate_payment(amount, user, host, next_url)
        if data is None:
            return 502, "Failed to connect to PhonePe."
    else:
        data = {"amount": amount, "currency": "INR", "transaction_id": transaction_id}

    data.update(
        {
            "start_date": start_date,
            "end_date": end_date,
            "user": user,
            "players": [player] if not group_payment else players,
            "event": event,
        }
    )
    if gateway == PaymentGateway.RAZORPAY:
        RazorpayTransaction.create_from_order_data(data)
        transaction_user_name = user.get_full_name()
        description = (
            f"Membership for {player.user.get_full_name()}"
            if not group_payment
            else f"Membership group payment by {transaction_user_name} for {player_names}"
        )
        if len(description) > RAZORPAY_DESCRIPTION_MAX:
            description = description[:250] + "..."
        extra_data = {
            "name": settings.APP_NAME,
            "image": settings.LOGO_URL,
            "description": description,
            "prefill": {"name": user.get_full_name(), "email": user.email, "contact": user.phone},
        }
        data.update(extra_data)
    elif gateway == PaymentGateway.PHONEPE:
        PhonePeTransaction.create_from_order_data(data)
    elif gateway == PaymentGateway.MANUAL:
        ManualTransaction.create_from_order_data(data)
        memberships = Membership.objects.filter(
            player__in=player_ids if group_payment else [player.id]
        )
        memberships.update(is_active=True, start_date=start_date, end_date=end_date)
    else:
        # We shouldn't get here, because enum
        pass

    return 200, data


@api.post(
    "/payment-success", response={200: list[PlayerSchema], 502: str, 404: Response, 422: Response}
)
def payment_success(
    request: AuthenticatedHttpRequest, payment: PaymentFormSchema
) -> tuple[int, QuerySet[Player] | message_response | str]:
    authentic = verify_razorpay_payment(payment.dict())
    if not authentic:
        return 422, {"message": "We were unable to ascertain the authenticity of the payment."}
    transaction = update_razorpay_transaction(payment)
    if not transaction:
        return 404, {"message": "No order found."}
    return 200, transaction.players.all()


@api.get(
    "/phonepe-transaction/{transaction_id}",
    response={200: PhonePeTransactionSchema, 400: Response, 422: Response, 502: str},
)
def get_phonepe_transaction(
    request: AuthenticatedHttpRequest,
    transaction_id: str,
) -> tuple[int, message_response | PhonePeTransaction]:
    try:
        transaction = PhonePeTransaction.objects.get(transaction_id=transaction_id)
    except PhonePeTransaction.DoesNotExist:
        return 422, {"message": "PhonePe Transaction does not exist!"}

    # Check transaction status with PhonePe for pending transactions
    if transaction.status == PhonePeTransaction.TransactionStatusChoices.PENDING:
        check_and_update_phonepe_transaction(transaction)

    return 200, transaction


@api.post("/phonepe-callback", auth=None, response={200: Response})
@csrf_exempt
def phonepe_callback(request: HttpRequest) -> message_response:
    body = request.body.decode("utf8")
    signature = request.headers.get("X-Verify", "")
    if not verify_callback_checksum(body, signature):
        return {"message": "Signature could not be verified"}

    encoded_data = json.loads(body)["response"]
    data = json.loads(b64decode(encoded_data).decode("utf8"))
    code = data["code"]
    prefix = "PAYMENT_"
    if not code.startswith(prefix):
        return {"message": "Ignored webhook"}
    code = code[len(prefix) :]
    transaction_id = data["data"]["merchantTransactionId"]
    try:
        transaction = PhonePeTransaction.objects.get(transaction_id=transaction_id)
    except PhonePeTransaction.DoesNotExist:
        return {"message": "Transaction not found"}
    update_phonepe_transaction(transaction, code)
    return {"message": "Webhook processed"}


def check_and_update_phonepe_transaction(transaction: PhonePeTransaction) -> None:
    data = check_transaction_status(str(transaction.transaction_id))
    code = data["code"]
    prefix = "PAYMENT_"
    if code.startswith(prefix):
        code = code[len(prefix) :]
        if transaction.status != code.lower():
            update_phonepe_transaction(transaction, code)


def update_phonepe_transaction(
    transaction: PhonePeTransaction, status_code: str
) -> PhonePeTransaction:
    transaction.status = getattr(PhonePeTransaction.TransactionStatusChoices, status_code)
    transaction.save(update_fields=["status"])
    if transaction.status == PhonePeTransaction.TransactionStatusChoices.SUCCESS:
        update_transaction_player_memberships(transaction)
    return transaction


def update_razorpay_transaction(payment: PaymentFormSchema) -> RazorpayTransaction | None:
    try:
        transaction = RazorpayTransaction.objects.get(order_id=payment.razorpay_order_id)
    except RazorpayTransaction.DoesNotExist:
        return None

    n = len("razorpay_")
    for key, value in payment.dict().items():
        setattr(transaction, key[n:], value)
    return mark_transaction_completed(transaction)


def mark_transaction_completed(transaction: RazorpayTransaction) -> RazorpayTransaction:
    transaction.status = RazorpayTransaction.TransactionStatusChoices.COMPLETED
    transaction.save()
    update_transaction_player_memberships(transaction)
    return transaction


def update_transaction_player_memberships(
    transaction: RazorpayTransaction | PhonePeTransaction,
) -> None:
    membership_defaults = {
        "start_date": transaction.start_date,
        "end_date": transaction.end_date,
        "event": transaction.event,
        "is_active": True,
    }
    for player in transaction.players.all():
        membership, created = Membership.objects.get_or_create(
            player=player, defaults=membership_defaults
        )
        if not created:
            for key, value in membership_defaults.items():
                setattr(membership, key, value)
            membership.save()


@api.post("/payment-success-webhook", auth=None, response={200: Response})
@csrf_exempt
def payment_webhook(request: HttpRequest) -> message_response:
    body = request.body.decode("utf8")
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not verify_razorpay_webhook_payload(body, signature):
        return {"message": "Signature could not be verified"}
    data = json.loads(body)["payload"]["payment"]["entity"]
    payment = PaymentFormSchema(
        razorpay_payment_id=data["id"],
        razorpay_order_id=data["order_id"],
        razorpay_signature=f"webhook_{signature}",
    )
    update_razorpay_transaction(payment)
    return {"message": "Webhook processed"}


@api.get("/transactions", response={200: list[dict[str, Any]]})
def list_transactions(
    request: AuthenticatedHttpRequest,
    user_only: bool = True,
    only_invalid: bool = False,
    only_manual: bool = False,
) -> list[dict[str, Any]]:
    user = request.user
    payment_type_schema_map = {
        PaymentGateway.MANUAL: ManualTransactionSchema,
        PaymentGateway.RAZORPAY: RazorpayTransactionSchema,
        PaymentGateway.PHONEPE: PhonePeTransactionSchema,
    }
    response_data = []
    for payment_type, schema in payment_type_schema_map.items():
        if only_manual and payment_type != PaymentGateway.MANUAL:
            continue
        transactions = list_transactions_by_type(user, payment_type, user_only, only_invalid)
        transaction_dicts = [schema.from_orm(t).dict() for t in transactions]
        for d in transaction_dicts:
            d["type"] = payment_type.value
            if "payment_date" not in d:
                d["payment_date"] = d["transaction_date"]

        response_data.extend(transaction_dicts)
    return response_data


def list_transactions_by_type(
    user: User, payment_type: PaymentGateway, user_only: bool = True, only_invalid: bool = False
) -> QuerySet[Model]:
    transaction_classes = {
        PaymentGateway.MANUAL: ManualTransaction,
        PaymentGateway.RAZORPAY: RazorpayTransaction,
        PaymentGateway.PHONEPE: PhonePeTransaction,
    }
    Cls = transaction_classes[payment_type]  # noqa: N806
    order_by = (
        "-payment_date"
        if payment_type in {PaymentGateway.MANUAL, PaymentGateway.RAZORPAY}
        else "-transaction_date"
    )

    if not user_only and user.is_staff:
        transactions = Cls.objects.filter(validated=False) if only_invalid else Cls.objects.all()

    else:
        # Get ids of all associated players of a user (player + wards)
        ward_ids = set(user.guardianship_set.values_list("player_id", flat=True))
        player_id = set(Player.objects.filter(user=user).values_list("id", flat=True))
        player_ids = ward_ids.union(player_id)

        query = Q(user=user) | Q(players__in=player_ids)
        transactions = Cls.objects.filter(query)
        if only_invalid:
            transactions = transactions.filter(validated=False)

    return transactions.distinct().order_by(order_by)


@api.post(
    "/validate-transactions", response={200: ValidationStatsSchema, 400: Response, 401: Response}
)
def validate_transactions(
    request: AuthenticatedHttpRequest,
    bank_statement: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, message_response] | tuple[int, dict[str, int]]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can validate transactions"}

    if not bank_statement.name or not bank_statement.name.endswith(".csv"):
        return 400, {"message": "Please upload a CSV file!"}

    text = bank_statement.read().decode("utf-8")
    stats = validate_manual_transactions(io.StringIO(text))
    return 200, stats


@api.post(
    "/validate-transaction", response={200: ManualTransactionSchema, 400: Response, 401: Response}
)
def validate_transaction(
    request: AuthenticatedHttpRequest, data: ManualTransactionValidationFormSchema
) -> tuple[int, message_response] | tuple[int, ManualTransaction]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can validate transactions"}

    try:
        transaction = ManualTransaction.objects.get(transaction_id=data.transaction_id)
    except Player.DoesNotExist:
        return 400, {"message": "Transaction does not exist"}

    transaction.validation_comment = data.validation_comment
    transaction.validated = True
    transaction.save(update_fields=["validation_comment", "validated"])
    return 200, transaction


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

    try:
        is_minor = bool(player.guardianship)
    except Guardianship.DoesNotExist:
        is_minor = False

    if is_minor and request.user == player.user:
        return 400, {"message": "Waiver can only signed by a guardian"}

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


@api.post(
    "/tournament/{event_id}/add-to-roster",
    response={200: TournamentPlayerRegistrationSchema, 400: Response, 401: Response},
)
def add_player_to_roster(
    request: AuthenticatedHttpRequest,
    event_id: int,
    registration_details: AddToRosterSchema,
) -> tuple[int, Registration] | tuple[int, message_response]:
    try:
        team = Team.objects.get(id=registration_details.team_id)
        event = Event.objects.get(id=event_id)
        tournament = Tournament.objects.get(event=event)
    except (Event.DoesNotExist, Team.DoesNotExist, Tournament.DoesNotExist):
        return 400, {"message": "Team/Event/Tournament does not exist"}

    if tournament.status != Tournament.Status.REGISTERING:
        return 400, {
            "message": f"You can't roster players now ! Rostering open from {tournament.event.registration_start_date} to {tournament.event.registration_start_date}"
        }

    if team not in tournament.teams.all():
        return 400, {"message": f"{team.name} is not registered for ${event.title} !"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can roster players to the team"}

    try:
        player = Player.objects.get(id=registration_details.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    if registration_details.role not in Registration.Role._value2member_map_:
        return 400, {"message": "Invalid role"}

    registration = Registration(
        event=event,
        team=team,
        player=player,
        is_playing=registration_details.is_playing,
        role=registration_details.role,
    )
    registration.save()

    return 200, registration


@api.put(
    "/tournament/remove-from-roster/{registration_id}",
    response={200: Response, 400: Response, 401: Response},
)
def remove_from_roster(
    request: AuthenticatedHttpRequest,
    registration_id: int,
    registration_details: RemoveFromRosterSchema,
) -> tuple[int, message_response]:
    try:
        event = Event.objects.get(id=registration_details.event_id)
        team = Team.objects.get(id=registration_details.team_id)
        tournament = Tournament.objects.get(event=event)
    except (Event.DoesNotExist, Team.DoesNotExist, Tournament.DoesNotExist):
        return 400, {"message": "Team/Event/Tournament does not exist"}

    if tournament.status != Tournament.Status.REGISTERING:
        return 400, {
            "message": f"You can't roster players now ! Rostering open from {tournament.event.registration_start_date} to {tournament.event.registration_start_date}"
        }

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can remove players from the roster"}

    try:
        registration = Registration.objects.get(id=registration_id, event=event, team=team)
        registration.delete()
        return 200, {"message": "Player registration removed succesfully"}

    except Registration.DoesNotExist:
        return 400, {"message": "Registration does not exist"}


@api.put(
    "tournament/roster/update-registration/{registration_id}",
    response={200: TournamentPlayerRegistrationSchema, 400: Response, 401: Response},
)
def update_registration(
    request: AuthenticatedHttpRequest,
    registration_id: int,
    registration_details: TournamentPlayerRegistrationUpdateSchema,
) -> tuple[int, Registration] | tuple[int, message_response]:
    try:
        event = Event.objects.get(id=registration_details.event_id)
        team = Team.objects.get(id=registration_details.team_id)
        tournament = Tournament.objects.get(event=event)
    except (Event.DoesNotExist, Team.DoesNotExist, Tournament.DoesNotExist):
        return 400, {"message": "Team/Event/Tournament does not exist"}

    if tournament.status != Tournament.Status.REGISTERING:
        return 400, {
            "message": f"You can't edit registrations now ! Rostering open from {tournament.event.registration_start_date} to {tournament.event.registration_start_date}"
        }

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can remove players from the roster"}

    try:
        registration = Registration.objects.get(id=registration_id, event=event, team=team)
    except Registration.DoesNotExist:
        return 400, {"message": "Registration does not exist"}

    if registration_details.is_playing:
        registration.is_playing = registration_details.is_playing

    if registration_details.role:
        if registration_details.role not in Registration.Role._value2member_map_:
            return 400, {"message": "Invalid role"}
        registration.role = registration_details.role

    registration.save()
    return 200, registration


@api.get("/tournament/roster", auth=None, response={200: list[UCRegistrationSchema], 400: Response})
def get_tournament_team_roster(
    request: AuthenticatedHttpRequest, tournament_slug: str, team_slug: str
) -> tuple[int, list[UCRegistration] | message_response]:
    try:
        event = Event.objects.get(slug=tournament_slug)
        team = Team.objects.get(slug=team_slug)
        uc_registrations = UCRegistration.objects.filter(team=team, event=event).order_by(
            "person__first_name"
        )

        registrations = Registration.objects.filter(event=event, team=team).order_by(
            "player__user__first_name"
        )

        def _reg_to_uc_reg(reg: Registration) -> UCRegistration:
            if reg.player.ultimate_central_id:
                person = UCPerson.objects.get(id=reg.player.ultimate_central_id)
            else:
                person = UCPerson(
                    email=reg.player.user.email,
                    first_name=reg.player.user.first_name,
                    last_name=reg.player.user.last_name,
                    slug="",
                    dominant_hand="",
                    image_url="",
                )

            roles = []
            role_label = Registration.Role._value2member_map_[reg.role].label  # type: ignore[attr-defined]
            roles.append(role_label)

            if reg.is_playing:
                roles.append("player")

            return UCRegistration(
                id=reg.id, event=reg.event, team=reg.team, person=person, roles=roles
            )

        regs_to_uc_regs = list(map(_reg_to_uc_reg, registrations))

        if uc_registrations.count() == 0:
            return 200, regs_to_uc_regs
        else:
            return 200, list(uc_registrations)

    except (Event.DoesNotExist, Team.DoesNotExist):
        return 400, {"message": "Tournament/Team does not exist"}


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
        tournament_details.registration_start_date, tournament_details.registration_end_date
    ):
        return 400, {"message": "Registration Start date can't be after Registration end date"}

    if if_dates_are_not_in_order(
        tournament_details.registration_end_date, tournament_details.start_date
    ):
        return 400, {"message": "Registration End date can't be after Tournament Start date"}

    event = Event(
        title=tournament_details.title,
        start_date=tournament_details.start_date,
        end_date=tournament_details.end_date,
        registration_start_date=tournament_details.registration_start_date,
        registration_end_date=tournament_details.registration_end_date,
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

    if if_today(tournament_details.registration_start_date):
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
        return 400, {
            "message": f"You can't register a team now ! Teams can be registered from {tournament.event.registration_start_date} to {tournament.event.registration_start_date}"
        }

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
        return 400, {
            "message": f"You can't de-register a team now ! Teams can be registered from {tournament.event.registration_start_date} to {tournament.event.registration_start_date}"
        }

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

    if match_details.video_url:
        match.video_url = match_details.video_url

    if match_details.duration_mins:
        match.duration_mins = match_details.duration_mins

    if match_details.spirit_score_team_1:
        match.spirit_score_team_1 = create_spirit_scores(match_details.spirit_score_team_1)

    if match_details.spirit_score_team_2:
        match.spirit_score_team_2 = create_spirit_scores(match_details.spirit_score_team_2)

    if match_details.self_spirit_score_team_1:
        match.self_spirit_score_team_1 = create_spirit_scores(
            match_details.self_spirit_score_team_1
        )

    if match_details.self_spirit_score_team_2:
        match.self_spirit_score_team_2 = create_spirit_scores(
            match_details.self_spirit_score_team_2
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

    if match.team_1 is not None and match.team_1.id == spirit_score.team_id:
        match.spirit_score_team_2 = create_spirit_scores(spirit_score.opponent)
        match.self_spirit_score_team_1 = create_spirit_scores(spirit_score.self)
    elif match.team_2 is not None and match.team_2.id == spirit_score.team_id:
        match.spirit_score_team_1 = create_spirit_scores(spirit_score.opponent)
        match.self_spirit_score_team_2 = create_spirit_scores(spirit_score.self)
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

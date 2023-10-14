import contextlib
import datetime
import io
import json
import time
from typing import Any, cast

import firebase_admin
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.db.utils import IntegrityError
from django.http import HttpRequest
from django.utils.text import slugify
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from firebase_admin import auth
from ninja import File, NinjaAPI, UploadedFile
from ninja.security import django_auth

from server.constants import EVENT_MEMBERSHIP_AMOUNT, MEMBERSHIP_END, MEMBERSHIP_START
from server.firebase_middleware import firebase_to_django_user
from server.manual_transactions import validate_manual_transactions
from server.models import (
    Accreditation,
    Bracket,
    CrossPool,
    Event,
    Guardianship,
    ManualTransaction,
    Match,
    Membership,
    Player,
    Pool,
    PositionPool,
    RazorpayTransaction,
    SpiritScore,
    Team,
    Tournament,
    UCPerson,
    UCRegistration,
    User,
    Vaccination,
)
from server.schema import (
    AccreditationFormSchema,
    AccreditationSchema,
    AnnualMembershipSchema,
    BracketCreateSchema,
    BracketSchema,
    Credentials,
    CrossPoolSchema,
    EventMembershipSchema,
    EventSchema,
    FirebaseCredentials,
    FirebaseSignUpCredentials,
    GroupMembershipSchema,
    GuardianshipFormSchema,
    ManualTransactionSchema,
    ManualTransactionValidationFormSchema,
    MatchCreateSchema,
    MatchSchema,
    MatchScoreSchema,
    MatchUpdateSchema,
    NotVaccinatedFormSchema,
    OrderSchema,
    PaymentFormSchema,
    PersonSchema,
    PlayerFormSchema,
    PlayerSchema,
    PlayerTinySchema,
    PoolCreateSchema,
    PoolSchema,
    PositionPoolCreateSchema,
    PositionPoolSchema,
    RegistrationGuardianSchema,
    RegistrationOthersSchema,
    RegistrationSchema,
    RegistrationWardSchema,
    Response,
    TeamSchema,
    TopScoreCredentials,
    TournamentCreateSchema,
    TournamentSchema,
    TournamentUpdateSeedingSchema,
    TransactionSchema,
    UCRegistrationSchema,
    UserFormSchema,
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
    get_new_bracket_seeding,
    get_new_pool_results,
    populate_fixtures,
    update_tournament_spirit_rankings,
)
from server.utils import (
    RAZORPAY_DESCRIPTION_MAX,
    RAZORPAY_NOTES_MAX,
    create_razorpay_order,
    verify_razorpay_payment,
    verify_razorpay_webhook_payload,
)

api = NinjaAPI(auth=django_auth, csrf=True)


class AuthenticatedHttpRequest(HttpRequest):
    user: User


message_response = dict[str, str]


# User #########


@api.get("/me", response={200: UserSchema})
def me(request: AuthenticatedHttpRequest) -> User:
    return request.user


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


@api.get("/team/{team_slug}", auth=None, response={200: TeamSchema, 400: Response})
def get_team(
    request: AuthenticatedHttpRequest, team_slug: str
) -> tuple[int, Team | message_response]:
    try:
        team = Team.objects.get(ultimate_central_slug=team_slug)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    return 200, team


# Login #########


@api.post("/login", auth=None, response={200: UserSchema, 403: Response})
def api_login(
    request: HttpRequest, credentials: Credentials
) -> tuple[int, AbstractBaseUser | message_response]:
    user = authenticate(request, username=credentials.username, password=credentials.password)
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


@api.post("/firebase-login", auth=None, response={200: UserSchema, 404: Response, 403: Response})
def firebase_login(
    request: HttpRequest, credentials: FirebaseCredentials | FirebaseSignUpCredentials
) -> tuple[int, User | message_response]:
    try:
        firebase_user = auth.get_user(credentials.uid)
    except (firebase_admin._auth_utils.UserNotFoundError, ValueError):
        # ValueError occurs when firebase_app wasn't initialized because no
        # server credentials
        firebase_user = None
    user = firebase_to_django_user(firebase_user)
    invalid_credentials = 403, {"message": "Invalid credentials"}
    if user is None and firebase_user is not None and isinstance(credentials, FirebaseCredentials):
        return 404, {"message": "User not found in the DB"}
    elif (
        user is None
        and firebase_user is not None
        and isinstance(credentials, FirebaseSignUpCredentials)
    ):
        # Create user when we have an email ID
        user = User.objects.create(
            email=credentials.email,
            username=credentials.email,
            first_name=credentials.first_name,
            last_name=credentials.last_name,
            phone=credentials.phone,
        )
    elif user is None:
        return invalid_credentials

    request.session["firebase_token"] = credentials.token
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
            person = UCPerson.objects.get(email=user.email)
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
        username=registration.email,  # type: ignore[attr-defined]
        defaults={
            "email": registration.email,  # type: ignore[attr-defined]
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
    email = registration.email  # type: ignore[attr-defined]
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
    email = registration.guardian_email
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

    if request.user.is_staff:
        registrations = UCRegistration.objects.filter(event=event)
    else:
        no_uc_profile = (400, {"message": "Need a linked UC profile"})
        try:
            player = request.user.player_profile
        except Player.DoesNotExist:
            return no_uc_profile

        if player.ultimate_central_id is None:
            return no_uc_profile

        team_ids = set(
            UCRegistration.objects.filter(
                event=event, person_id=player.ultimate_central_id
            ).values_list("team_id", flat=True)
        )
        registrations = UCRegistration.objects.filter(event=event, team_id__in=team_ids)

    return 200, registrations


# Payments ##########


@api.post(
    "/manual-transaction/{transaction_id}",
    response={200: ManualTransactionSchema, 400: Response, 502: str},
)
def create_manual_transaction(
    request: AuthenticatedHttpRequest,
    transaction_id: str,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    return create_transaction(request, order, transaction_id)


@api.post("/create-order", response={200: OrderSchema, 400: Response, 502: str})
def create_razorpay_transaction(
    request: AuthenticatedHttpRequest,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    return create_transaction(request, order)


def create_transaction(
    request: AuthenticatedHttpRequest,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
    transaction_id: str | None = None,
) -> tuple[int, str | message_response | dict[str, Any]]:
    if isinstance(order, GroupMembershipSchema):
        group_payment = True
        players = Player.objects.filter(id__in=order.player_ids)
        player_ids = {p.id for p in players}
        if len(player_ids) != len(order.player_ids):
            missing_players = set(order.player_ids) - player_ids
            return 400, {
                "message": f"Some players couldn't be found in the DB: {sorted(missing_players)}"
            }

    else:
        group_payment = False
        try:
            player = Player.objects.get(id=order.player_id)
        except Player.DoesNotExist:
            return 400, {"message": "Player does not exist!"}

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
            return 400, {"message": "Event does not exist!"}

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

    if transaction_id is None:
        data = create_razorpay_order(amount, receipt=receipt, notes=notes)
        if data is None:
            return 502, "Failed to connect to Razorpay."
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
    if not transaction_id:
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
    else:
        ManualTransaction.create_from_order_data(data)
        memberships = Membership.objects.filter(
            player__in=player_ids if group_payment else [player.id]
        )
        memberships.update(is_active=True, start_date=start_date, end_date=end_date)
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
    transaction = update_transaction(payment)
    if not transaction:
        return 404, {"message": "No order found."}
    return 200, transaction.players.all()


def update_transaction(payment: PaymentFormSchema) -> RazorpayTransaction | None:
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

    return transaction


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
    update_transaction(payment)
    return {"message": "Webhook processed"}


@api.get("/transactions", response={200: list[TransactionSchema]})
def list_transactions(
    request: AuthenticatedHttpRequest, include_all: bool = False, only_invalid: bool = False
) -> QuerySet[ManualTransaction]:
    user = request.user

    if include_all and user.is_staff:
        transactions = (
            ManualTransaction.objects.filter(validated=False)
            if only_invalid
            else ManualTransaction.objects.all()
        )

    else:
        # Get ids of all associated players of a user (player + wards)
        ward_ids = set(user.guardianship_set.values_list("player_id", flat=True))
        player_id = set(Player.objects.filter(user=user).values_list("id", flat=True))
        player_ids = ward_ids.union(player_id)

        query = Q(user=request.user) | Q(players__in=player_ids)
        transactions = ManualTransaction.objects.filter(query)
        if only_invalid:
            transactions = transactions.filter(validated=False)

    return transactions.distinct().order_by("-payment_date")


@api.post("/validate-transactions", response={200: ValidationStatsSchema, 400: Response})
def validate_transactions(
    request: AuthenticatedHttpRequest,
    bank_statement: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, message_response] | tuple[int, dict[str, int]]:
    if not bank_statement.name or not bank_statement.name.endswith(".csv"):
        return 400, {"message": "Please upload a CSV file!"}

    text = bank_statement.read().decode("utf-8")
    stats = validate_manual_transactions(io.StringIO(text))
    return 200, stats


@api.post("/validate-transaction", response={200: TransactionSchema, 400: Response})
def validate_transaction(
    request: AuthenticatedHttpRequest, data: ManualTransactionValidationFormSchema
) -> tuple[int, message_response] | tuple[int, ManualTransaction]:
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

    acc.full_clean()
    acc.save()
    return 200, acc


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
    """Get tournaments in reverse chronological order"""
    return 200, Tournament.objects.all().order_by("-event__end_date")


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
            event = Event.objects.get(ultimate_central_slug=slug)
            tournament = Tournament.objects.get(event=event)
    except (Tournament.DoesNotExist, Event.DoesNotExist):
        return 400, {"message": "Tournament does not exist"}

    return 200, tournament


@api.get("/tournament/roster", auth=None, response={200: list[PersonSchema], 400: Response})
def get_tournament_team_roster(
    request: AuthenticatedHttpRequest, tournament_slug: str, team_slug: str
) -> tuple[int, QuerySet[UCPerson] | message_response]:
    try:
        event = Event.objects.get(ultimate_central_slug=tournament_slug)
        team = Team.objects.get(ultimate_central_slug=team_slug)
        persons_list = (
            UCRegistration.objects.filter(team=team, event=event)
            .values_list("person", flat=True)
            .distinct()
        )
        players = UCPerson.objects.filter(id__in=persons_list).order_by("first_name")
        return 200, players
    except (Event.DoesNotExist, Team.DoesNotExist):
        return 400, {"message": "Tournament/Team does not exist"}


@api.get(
    "/tournament/slug/{slug}/matches", auth=None, response={200: list[MatchSchema], 400: Response}
)
def get_tournament_matches_by_slug(
    request: AuthenticatedHttpRequest, slug: str
) -> tuple[int, QuerySet[Match] | message_response]:
    try:
        event = Event.objects.get(ultimate_central_slug=slug)
        tournament = Tournament.objects.get(event=event)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}
    except Event.DoesNotExist:
        return 400, {"message": "Event does not exist"}

    return 200, Match.objects.filter(tournament=tournament).order_by("time")


@api.post("/tournament", response={200: TournamentSchema, 400: Response, 401: Response})
def create_tournament(
    request: AuthenticatedHttpRequest,
    tournament_details: TournamentCreateSchema,
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
    tournament.save()

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

    # FIXME Check if all teams in standings are there in rostered teams

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

    pool_seeding = {}
    pool_results = {}
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
            event = Event.objects.get(ultimate_central_slug=slug)
            tournament = Tournament.objects.get(event=event)
    except Tournament.DoesNotExist:
        return 400, {"message": "Tournament does not exist"}

    return 200, Pool.objects.filter(tournament=tournament)


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
            event = Event.objects.get(ultimate_central_slug=slug)
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
            event = Event.objects.get(ultimate_central_slug=slug)
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
            event = Event.objects.get(ultimate_central_slug=slug)
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

    match = Match(
        tournament=tournament,
        sequence_number=match_details.seq_num,
        time=match_datetime,
        field=match_details.field,
        placeholder_seed_1=match_details.seed_1,
        placeholder_seed_2=match_details.seed_2,
    )

    try:
        if match_details.stage == "pool":
            pool = Pool.objects.get(id=match_details.stage_id)
            match.pool = pool
        elif match_details.stage == "bracket":
            bracket = Bracket.objects.get(id=match_details.stage_id)
            match.bracket = bracket
        elif match_details.stage == "cross_pool":
            cross_pool = CrossPool.objects.get(id=match_details.stage_id)
            match.cross_pool = cross_pool
        elif match_details.stage == "position_pool":
            position_pool = PositionPool.objects.get(id=match_details.stage_id)
            match.position_pool = position_pool

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

    matches = Match.objects.filter(tournament=tournament).exclude(pool__isnull=True)

    for match in matches:
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

    match.score_team_1 = match_scores.team_1_score
    match.score_team_2 = match_scores.team_2_score

    if match.pool is not None:
        results = match.pool.results
        results = {int(k): v for k, v in results.items()}

        pool_seeding_list = list(map(int, match.pool.initial_seeding.keys()))
        pool_seeding_list.sort()
        tournament_seeding = match.tournament.current_seeding

        new_results, new_tournament_seeding = get_new_pool_results(
            results, match, pool_seeding_list, tournament_seeding
        )

        match.pool.results = new_results
        match.pool.save()

        match.tournament.current_seeding = new_tournament_seeding
        match.tournament.save()

    elif match.cross_pool is not None:
        seeding = match.cross_pool.current_seeding
        match.cross_pool.current_seeding = get_new_bracket_seeding(seeding, match)
        match.cross_pool.save()

        tournament_seeding = match.tournament.current_seeding
        match.tournament.current_seeding = get_new_bracket_seeding(tournament_seeding, match)
        match.tournament.save()

    elif match.bracket is not None:
        seeding = match.bracket.current_seeding
        match.bracket.current_seeding = get_new_bracket_seeding(seeding, match)
        match.bracket.save()

        tournament_seeding = match.tournament.current_seeding
        match.tournament.current_seeding = get_new_bracket_seeding(tournament_seeding, match)
        match.tournament.save()

    elif match.position_pool is not None:
        results = match.position_pool.results
        results = {int(k): v for k, v in results.items()}

        pool_seeding_list = list(map(int, match.position_pool.initial_seeding.keys()))
        pool_seeding_list.sort()
        tournament_seeding = match.tournament.current_seeding

        new_results, new_tournament_seeding = get_new_pool_results(
            results, match, pool_seeding_list, tournament_seeding
        )

        match.position_pool.results = new_results
        match.position_pool.save()

        match.tournament.current_seeding = new_tournament_seeding
        match.tournament.save()

    match.status = Match.Status.COMPLETED
    match.save()

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
    except Tournament.DoesNotExist:
        return 400, {"message": "Match does not exist"}

    if match_details.time:
        ind_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
        match_datetime = datetime.datetime.strptime(
            match_details.time, "%Y-%m-%dT%H:%M"
        ).astimezone(ind_tz)

        match.time = match_datetime

    if match_details.field:
        match.field = match_details.field

    if match_details.video_url:
        match.video_url = match_details.video_url

    if match_details.spirit_score_team_1:
        spirit_score = SpiritScore(
            rules=match_details.spirit_score_team_1.rules,
            fouls=match_details.spirit_score_team_1.fouls,
            fair=match_details.spirit_score_team_1.fair,
            positive=match_details.spirit_score_team_1.positive,
            communication=match_details.spirit_score_team_1.communication,
        )

        if match_details.spirit_score_team_1.mvp_id:
            mvp = UCPerson.objects.get(id=match_details.spirit_score_team_1.mvp_id)
            spirit_score.mvp = mvp

        if match_details.spirit_score_team_1.msp_id:
            msp = UCPerson.objects.get(id=match_details.spirit_score_team_1.msp_id)
            spirit_score.msp = msp

        spirit_score.save()

        match.spirit_score_team_1 = spirit_score

    if match_details.spirit_score_team_2:
        spirit_score = SpiritScore(
            rules=match_details.spirit_score_team_2.rules,
            fouls=match_details.spirit_score_team_2.fouls,
            fair=match_details.spirit_score_team_2.fair,
            positive=match_details.spirit_score_team_2.positive,
            communication=match_details.spirit_score_team_2.communication,
        )

        if match_details.spirit_score_team_2.mvp_id:
            mvp = UCPerson.objects.get(id=match_details.spirit_score_team_2.mvp_id)
            spirit_score.mvp = mvp

        if match_details.spirit_score_team_2.msp_id:
            msp = UCPerson.objects.get(id=match_details.spirit_score_team_2.msp_id)
            spirit_score.msp = msp

        spirit_score.save()

        match.spirit_score_team_2 = spirit_score

    if match_details.spirit_score_team_1 or match_details.spirit_score_team_2:
        update_tournament_spirit_rankings(match.tournament)

    match.save()

    return 200, match

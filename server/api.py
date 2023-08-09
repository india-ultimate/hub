import datetime
import json
import time
from typing import Any, cast

import firebase_admin
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.utils.text import slugify
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from firebase_admin import auth
from ninja import File, NinjaAPI, UploadedFile
from ninja.security import django_auth
from requests.exceptions import RequestException

from server.constants import (
    ANNUAL_MEMBERSHIP_AMOUNT,
    EVENT_MEMBERSHIP_AMOUNT,
    MEMBERSHIP_END,
    MEMBERSHIP_START,
)
from server.firebase_middleware import firebase_to_django_user
from server.models import (
    Event,
    Guardianship,
    Membership,
    Player,
    RazorpayTransaction,
    User,
    Vaccination,
)
from server.schema import (
    AnnualMembershipSchema,
    Credentials,
    EventMembershipSchema,
    EventSchema,
    FirebaseCredentials,
    FirebaseSignUpCredentials,
    GroupMembershipSchema,
    GuardianshipFormSchema,
    NotVaccinatedFormSchema,
    OrderSchema,
    PaymentFormSchema,
    PlayerFormSchema,
    PlayerSchema,
    PlayerTinySchema,
    RegistrationOthersSchema,
    RegistrationSchema,
    RegistrationWardSchema,
    Response,
    TransactionSchema,
    UserFormSchema,
    UserSchema,
    VaccinatedFormSchema,
    VaccinationSchema,
    WaiverFormSchema,
)
from server.utils import (
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
def list_players(request: AuthenticatedHttpRequest) -> list[PlayerTinySchema | PlayerSchema]:
    players = Player.objects.all()
    is_staff = request.user.is_staff
    if is_staff:
        return [PlayerSchema.from_orm(p) for p in players]
    else:
        return [PlayerTinySchema.from_orm(p) for p in players]


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
def api_logout(request: AuthenticatedHttpRequest) -> tuple[int, message_response]:
    logout(request)
    return 200, {"message": "Logged out"}


@api.post("/firebase-login", auth=None, response={200: UserSchema, 403: Response})
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
    if user is None and isinstance(credentials, FirebaseCredentials):
        return invalid_credentials
    elif user is None and isinstance(credentials, FirebaseSignUpCredentials):
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
    player.save()

    user_data = UserFormSchema(**registration.dict()).dict()
    for attr, value in user_data.items():
        setattr(user, attr, value)
    user.save()

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


# Events ##########


@api.get("/events", response={200: list[EventSchema]})
def list_events(request: AuthenticatedHttpRequest, include_all: bool = False) -> QuerySet[Event]:
    today = now().date()
    return Event.objects.all() if include_all else Event.objects.filter(start_date__gte=today)


# Payments ##########


@api.post("/create-order", response={200: OrderSchema, 400: Response, 502: str})
def create_order(
    request: AuthenticatedHttpRequest,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
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
            ANNUAL_MEMBERSHIP_AMOUNT * len(order.player_ids)
            if isinstance(order, GroupMembershipSchema)
            else ANNUAL_MEMBERSHIP_AMOUNT
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

    try:
        data = create_razorpay_order(amount, receipt=receipt, notes=notes)
    except RequestException:
        return 502, "Failed to connect to Razorpay."

    data.update(
        dict(
            start_date=start_date,
            end_date=end_date,
            user=user,
            players=[player] if not group_payment else players,
            event=event,
        )
    )
    RazorpayTransaction.create_from_order_data(data)
    transaction_user_name = user.get_full_name()
    description = (
        f"Membership for {player.user.get_full_name()}"
        if not group_payment
        else f"Membership group payment by {transaction_user_name} for {player_names}"
    )
    extra_data = {
        "name": settings.APP_NAME,
        "image": settings.LOGO_URL,
        "description": description,
        "prefill": {"name": user.get_full_name(), "email": user.email, "contact": user.phone},
    }
    data.update(extra_data)
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
def list_transactions(request: AuthenticatedHttpRequest) -> QuerySet[RazorpayTransaction]:
    user = request.user

    # Get ids of all associated players of a user (player + wards)
    ward_ids = set(user.guardianship_set.values_list("player_id", flat=True))
    player_id = set(Player.objects.filter(user=user).values_list("id", flat=True))
    player_ids = ward_ids.union(player_id)

    query = Q(user=request.user) | Q(players__in=player_ids)
    return RazorpayTransaction.objects.filter(query).distinct()


# Vaccination ##########


@api.post("/vaccination", response={200: VaccinationSchema, 400: Response})
def vaccination(
    request: AuthenticatedHttpRequest,
    vaccination: VaccinatedFormSchema | NotVaccinatedFormSchema,
    certificate: UploadedFile | None = File(None),
) -> tuple[int, Vaccination | message_response]:
    if vaccination.is_vaccinated and not certificate:
        return 400, {"message": "Certificate needs to be uploaded!"}

    try:
        player = Player.objects.get(id=vaccination.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    try:
        _vaccination = player.vaccination
        return 400, {"message": "Player's vaccination information is already available"}
    except Vaccination.DoesNotExist:
        pass

    vaccination_data = vaccination.dict()
    vaccination_data["certificate"] = certificate
    vaccination_data["player"] = player
    vaccine = Vaccination(**vaccination_data)
    vaccine.full_clean()
    vaccine.save()

    return 200, vaccine


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

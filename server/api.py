import datetime
import json
import time
from typing import List, Union

import firebase_admin
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from firebase_admin import auth
from ninja import NinjaAPI
from ninja.security import django_auth
from requests.exceptions import RequestException

from server.constants import (
    ANNUAL_MEMBERSHIP_AMOUNT,
    EVENT_MEMBERSHIP_AMOUNT,
    MEMBERSHIP_END,
    MEMBERSHIP_START,
)
from server.firebase_middleware import firebase_to_django_user
from server.models import Event, Guardianship, Membership, Player, RazorpayTransaction
from server.schema import (
    AnnualMembershipSchema,
    Credentials,
    EventMembershipSchema,
    EventSchema,
    FirebaseCredentials,
    OrderSchema,
    PaymentFormSchema,
    PlayerFormSchema,
    PlayerSchema,
    RegistrationOthersSchema,
    RegistrationSchema,
    RegistrationWardSchema,
    Response,
    UserFormSchema,
    UserSchema,
)
from server.utils import (
    create_razorpay_order,
    verify_razorpay_payment,
    verify_razorpay_webhook_payload,
)

User = get_user_model()

api = NinjaAPI(auth=django_auth, csrf=True)


@api.get("/user")
def current_user(request, response={200: UserSchema}):
    return UserSchema.from_orm(request.user)


@api.post("/login", auth=None, response={200: UserSchema, 403: Response})
def api_login(request, credentials: Credentials):
    user = authenticate(request, username=credentials.username, password=credentials.password)
    if user is not None:
        login(request, user)
        return 200, UserSchema.from_orm(user)
    else:
        return 403, {"message": "Invalid credentials"}


@api.post("/logout")
def api_logout(request):
    logout(request)
    return 200, {"message": "Logged out"}


@api.post("/firebase-login", auth=None, response={200: UserSchema, 403: Response})
def firebase_login(request, credentials: FirebaseCredentials):
    try:
        firebase_user = auth.get_user(credentials.uid)
    except (firebase_admin._auth_utils.UserNotFoundError, ValueError):
        # ValueError occurs when firebase_app wasn't initialized because no
        # server credentials
        firebase_user = None
    user = firebase_to_django_user(firebase_user)
    invalid_credentials = 403, {"message": "Invalid credentials"}
    if user is None:
        # FIXME: Decide on how to handle new sign-ups
        return invalid_credentials

    request.session["firebase_token"] = credentials.token
    request.user = user
    login(request, user)
    return 200, UserSchema.from_orm(user)


@api.post("/registration", response={200: PlayerSchema, 400: Response})
def register_self(request, registration: RegistrationSchema):
    return do_register(request.user, registration)


def do_register(
    user,
    registration: Union[RegistrationSchema, RegistrationOthersSchema, RegistrationWardSchema],
    guardian=None,
):
    try:
        Player.objects.get(user=user)
        return 400, {"message": "Player already exists"}
    except Player.DoesNotExist:
        player_data = PlayerFormSchema(**registration.dict()).dict()
        player = Player(**player_data, user=user)
        player.save()

        user_data = UserFormSchema(**registration.dict()).dict()
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        if guardian:
            Guardianship.objects.create(
                user=guardian, player=player, relation=registration.relation
            )

        return 200, PlayerSchema.from_orm(player)


@api.post("/registration/others", response={200: PlayerSchema, 400: Response})
def register_others(request, registration: RegistrationOthersSchema):
    user, created = User.objects.get_or_create(
        username=registration.email,
        defaults={
            "email": registration.email,
            "phone": registration.phone,
            "first_name": registration.first_name,
            "last_name": registration.last_name,
        },
    )
    return do_register(user, registration)


@api.post("/registration/ward", response={200: PlayerSchema, 400: Response})
def register_ward(request, registration: RegistrationWardSchema):
    email = registration.email
    if email is None:
        email = slugify(f"{registration.first_name} {registration.last_name}")
    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            "email": email,
            "phone": registration.phone,
            "first_name": registration.first_name,
            "last_name": registration.last_name,
        },
    )
    return do_register(user, registration, guardian=request.user)


# Events


@api.get("/events")
def list_events(request, include_all: bool = False, response={200: List[EventSchema]}):
    today = datetime.date.today()
    events = Event.objects.all() if include_all else Event.objects.filter(start_date__gte=today)
    return [EventSchema.from_orm(e) for e in events]


# Payments


@api.post("/create-order", response={200: OrderSchema, 400: Response, 502: str})
def create_order(request, order: Union[AnnualMembershipSchema, EventMembershipSchema]):
    try:
        player = Player.objects.get(id=order.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist!"}

    if isinstance(order, AnnualMembershipSchema):
        start_date = datetime.date(order.year, *MEMBERSHIP_START)
        end_date = datetime.date(order.year + 1, *MEMBERSHIP_END)
        is_annual = True
        event = None
        amount = ANNUAL_MEMBERSHIP_AMOUNT

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
    except RequestException as e:
        return 502, "Failed to connect to Razorpay."

    data.update(
        dict(
            start_date=start_date,
            end_date=end_date,
            user=user,
            membership=membership,
            event=event,
        )
    )
    transaction = RazorpayTransaction.create_from_order_data(data)
    extra_data = {
        "name": settings.APP_NAME,
        "image": settings.LOGO_URL,
        "description": f"Membership for {player.user.get_full_name()}",
        "prefill": {"name": user.get_full_name(), "email": user.email, "contact": user.phone},
    }
    data.update(extra_data)
    return data


@api.post("/payment-success", response={200: PlayerSchema, 502: str, 404: Response, 422: Response})
def payment_success(request, payment: PaymentFormSchema):
    authentic = verify_razorpay_payment(payment.dict())
    if not authentic:
        return 422, {"message": "We were unable to ascertain the authenticity of the payment."}
    transaction = update_transaction(payment)
    if not transaction:
        return 404, {"message": "No order found."}
    return PlayerSchema.from_orm(transaction.membership.player)


def update_transaction(payment):
    try:
        transaction = RazorpayTransaction.objects.get(order_id=payment.razorpay_order_id)
    except RazorpayTransaction.DoesNotExist:
        return None

    n = len("razorpay_")
    for key, value in payment.dict().items():
        setattr(transaction, key[n:], value)
    transaction.status = RazorpayTransaction.TransactionStatusChoices.COMPLETED
    transaction.save()
    membership = transaction.membership
    membership.start_date = transaction.start_date
    membership.end_date = transaction.end_date
    membership.event = transaction.event
    membership.is_active = True
    membership.save()
    return transaction


@api.post("/payment-success-webhook", auth=None, response={200: Response})
@csrf_exempt
def payment_webhook(request):
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

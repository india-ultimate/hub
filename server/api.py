import datetime
import time

import firebase_admin
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from firebase_admin import auth
from ninja import NinjaAPI
from ninja.security import django_auth
from requests.exceptions import RequestException

from server.constants import MEMBERSHIP_AMOUNT, MEMBERSHIP_END, MEMBERSHIP_START
from server.firebase_middleware import firebase_to_django_user
from server.models import Membership, Player, RazorpayTransaction
from server.schema import (
    Credentials,
    FirebaseCredentials,
    OrderFormSchema,
    OrderSchema,
    PaymentFormSchema,
    PlayerFormSchema,
    PlayerSchema,
    RegistrationSchema,
    Response,
    UserFormSchema,
    UserSchema,
)
from server.utils import create_razorpay_order, verify_razorpay_payment

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
def register_player(request, registration: RegistrationSchema):
    user = request.user

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

        return 200, PlayerSchema.from_orm(player)


# Payments


@api.post("/create-order", response={200: OrderSchema, 400: Response, 502: str})
def create_order(request, order: OrderFormSchema):
    user = request.user

    try:
        player = Player.objects.get(id=order.player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist!"}

    start_date = datetime.date(order.year, *MEMBERSHIP_START)
    end_date = datetime.date(order.year + 1, *MEMBERSHIP_END)

    try:
        membership = player.membership
    except Membership.DoesNotExist:
        membership = Membership.objects.create(
            player=player,
            is_annual=True,
            start_date=start_date,
            end_date=end_date,
            is_active=False,
        )

    ts = round(time.time())
    receipt = f"{membership.membership_number}:{start_date}:{ts}"
    notes = {
        "user_id": user.id,
        "player_id": player.id,
        "membership_id": membership.id,
    }
    try:
        data = create_razorpay_order(MEMBERSHIP_AMOUNT, receipt=receipt, notes=notes)
    except RequestException as e:
        return 502, "Failed to connect to Razorpay."

    data.update(dict(start_date=start_date, end_date=end_date))
    transaction = RazorpayTransaction.create_from_order_data(data, user, membership)
    extra_data = {
        "name": settings.APP_NAME,
        "image": settings.LOGO_URL,
        "description": f"{order.type.title()} for {player.user.get_full_name()}",
        "prefill": {"name": user.get_full_name(), "email": user.email, "contact": user.phone},
    }
    data.update(extra_data)
    return data


@api.post("/payment-success", response={200: PlayerSchema, 502: str, 404: Response, 422: Response})
def payment_success(request, payment: PaymentFormSchema):
    # FIXME: This API end-point could potentially also be used by the webhook
    # for on payment success. no CSRF, no auth
    try:
        transaction = RazorpayTransaction.objects.get(order_id=payment.razorpay_order_id)
    except RazorpayTransaction.DoesNotExist:
        return 404, {"message": "No order found."}

    try:
        authentic = verify_razorpay_payment(payment.dict())
    except RequestException as e:
        return 502, "Failed to connect to Razorpay."

    if authentic:
        n = len("razorpay_")
        for key, value in payment.dict().items():
            setattr(transaction, key[n:], value)
        transaction.status = RazorpayTransaction.TransactionStatusChoices.COMPLETED
        transaction.save()
        transaction.membership.start_date = transaction.start_date
        transaction.membership.end_date = transaction.end_date
        transaction.membership.is_active = True
        transaction.membership.save()
        response = PlayerSchema.from_orm(transaction.membership.player)
    else:
        transaction.status = RazorpayTransaction.TransactionStatusChoices.FAILED
        transaction.save()
        response = 422, {"message": "We were unable to ascertain the authenticity of the payment."}
    return response

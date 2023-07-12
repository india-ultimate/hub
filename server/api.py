import firebase_admin
from django.contrib.auth import authenticate, get_user_model, login, logout
from firebase_admin import auth
from ninja import NinjaAPI
from ninja.security import django_auth

from server.firebase_middleware import firebase_to_django_user
from server.models import Player
from server.schema import (
    Credentials,
    FirebaseCredentials,
    PlayerFormSchema,
    PlayerSchema,
    RegistrationSchema,
    Response,
    UserFormSchema,
    UserSchema,
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

from django.contrib.auth import authenticate, get_user_model, login, logout
from firebase_admin import auth
from ninja import ModelSchema, NinjaAPI, Schema
from ninja.security import django_auth
from ninja import ModelSchema
from .models import Player, User

from server.firebase_middleware import firebase_to_django_user

User = get_user_model()

api = NinjaAPI(auth=django_auth, csrf=True)


class Credentials(Schema):
    username: str
    password: str


class FirebaseCredentials(Schema):
    token: str
    uid: str


class Response(Schema):
    message: str


class UserSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["username"]


class PlayerSchema(ModelSchema):
    class Config:
        model = Player
        model_exclude = ['guardian'] # FIXME: Confirm what should be excluded and what are optional
        model_fields_optional = "__all__"


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
    except ValueError:
        # In case, firebase_app wasn't initialized because no server credentials
        firebase_user = None
    user = firebase_to_django_user(firebase_user)
    invalid_credentials = 403, {"message": "Invalid credentials"}
    if user is None:
        # FIXME: Decide on how to handle new sign-ups
        return invalid_credentials

    request.session["firebase_token"] = credentials.token
    request.user = user
    return 200, UserSchema.from_orm(user)

@api.post("/registration", response={200: Response, 400: Response})
def register_player(request, player: PlayerSchema):
    user = request.user
    try:
        Player.objects.get(user=user)
        return 400, {"message": "Player already exists"}
    except Player.DoesNotExist:
        player_instance = Player(**player.dict())
        player_instance.user = user
        player_instance.save()
        return 200, {"message": "Player successfully submitted"}

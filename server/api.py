from django.contrib.auth import authenticate, get_user_model, login, logout
from firebase_admin import auth
from ninja import ModelSchema, NinjaAPI, Schema
from ninja.security import django_auth

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
def api_login(request):
    logout(request)


@api.post("/firebase-login", auth=None, response={200: UserSchema, 403: Response})
def login(request, credentials: FirebaseCredentials):
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

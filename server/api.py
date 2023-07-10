from django.contrib.auth import authenticate, get_user_model, login, logout
from ninja import ModelSchema, NinjaAPI, Schema
from ninja.security import django_auth

User = get_user_model()

api = NinjaAPI(auth=django_auth, csrf=True)


class Credentials(Schema):
    username: str
    password: str


class Response(Schema):
    message: str


class UserSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["username"]


@api.get("/user")
def current_user(request, response={200: UserSchema}):
    return UserSchema.from_orm(request.user)


@api.post("/login", auth=None, response={200: Response, 403: Response})
def api_login(request, credentials: Credentials):
    user = authenticate(request, username=credentials.username, password=credentials.password)
    if user is not None:
        login(request, user)
        return 200, {"message": "Login successful"}
    else:
        return 403, {"message": "Invalid credentials"}


@api.post("/logout")
def api_login(request):
    logout(request)

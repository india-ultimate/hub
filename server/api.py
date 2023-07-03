from django.contrib.auth import authenticate, login
from ninja import NinjaAPI, Schema
from ninja.security import django_auth

api = NinjaAPI(auth=django_auth, csrf=True)


class Credentials(Schema):
    username: str
    password: str


class Response(Schema):
    message: str


@api.get("/user")
def current_user(request):
    return f"Authenticated user {request.auth}"


@api.post("/login", auth=None, response={200: Response, 403: Response})
def login(request, credentials: Credentials):
    user = authenticate(request, username=credentials.username, password=credentials.password)
    if user is not None:
        login(request, user)
        return 200, {"message": "Login successful"}
    else:
        return 403, {"message": "Invalid credentials"}

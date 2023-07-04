from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
from ninja import Form, NinjaAPI, Schema
from ninja.security import django_auth

api = NinjaAPI(auth=django_auth, csrf=True)


class Credentials(Schema):
    username: str
    password: str


class Response(Schema):
    message: str


class WAMessage(Schema):
    NumMedia: int
    From: str
    Body: str


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


@api.post("/whatsapp-message", auth=None)
@csrf_exempt
def login(request, message: WAMessage = Form(...)):
    print(message)
    print(request.POST)

    # TODO: Check if sender is_admin (or maybe is_staff) using phone number in
    # the message.

    # For validated messages, create a Post object in the DB, with author as
    # sender and with a creation timestamp.

    # These messages can be displayed in the UI to authenticated users?

    return {"message": "Received message"}

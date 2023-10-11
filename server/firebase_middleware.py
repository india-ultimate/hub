import base64
import json
import os
from pathlib import Path
from typing import Any

import firebase_admin
from django.http import HttpRequest, HttpResponse
from firebase_admin import auth, credentials

from server.models import User


def firebase_to_django_user(firebase_user: auth.UserRecord) -> User | None:
    if firebase_user is None:
        return None

    phone = firebase_user.phone_number
    email = firebase_user.email
    if not (phone or email):
        return None

    query = {"email": email} if email else {"phone": phone}

    try:
        user = User.objects.get(**query)
    except User.DoesNotExist:
        return None

    return user


class FirebaseAuthenticationMiddleware:
    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.initialize_firebase_app()

        # Check if the user is authenticated with Firebase
        firebase_token = request.session.get("firebase_token")
        if firebase_token:
            try:
                decoded_token = auth.verify_id_token(firebase_token)
                uid = decoded_token["uid"]
                firebase_user = auth.get_user(uid)
                user = firebase_to_django_user(firebase_user)
                if user is not None:
                    request.user = user
            except (auth.InvalidIdTokenError, ValueError):
                # Invalid token, user is not authenticated
                pass

        response = self.get_response(request)
        return response

    def initialize_firebase_app(self) -> None:
        # In tests, the middleware is instantiated multiple times and causes
        # firebase initialization errors. This ensures that the initialization
        # only happens when required.
        try:
            self.firebase_app = firebase_admin.get_app()
            return
        except ValueError:
            pass

        credentials_file = Path("secrets/serviceAccountKey.json")
        env_var = "FIREBASE_SERVICE_ACCOUNT_CREDENTIALS"
        if credentials_file.exists():
            with credentials_file.open() as f:
                credentials_data = json.load(f)
        elif os.environ.get(env_var):
            credentials_data = json.loads(base64.b64decode(os.environ[env_var]))
        else:
            credentials_data = None

        if credentials_data:
            cred = credentials.Certificate(credentials_data)
            self.firebase_app = firebase_admin.initialize_app(cred)

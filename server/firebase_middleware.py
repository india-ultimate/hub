from pathlib import Path

import firebase_admin
from django.contrib.auth import get_user_model
from firebase_admin import auth, credentials

User = get_user_model()


def firebase_to_django_user(firebase_user):
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
    def __init__(self, get_response):
        self.get_response = get_response
        self.firebase_app = None

    def __call__(self, request):
        if not self.firebase_app:
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

    def initialize_firebase_app(self):
        credentials_file = Path("secrets/serviceAccountKey.json")
        if credentials_file.exists():
            cred = credentials.Certificate(str(credentials_file))
            self.firebase_app = firebase_admin.initialize_app(cred)

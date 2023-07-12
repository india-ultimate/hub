from django.contrib.auth import get_user_model
from ninja import ModelSchema, Schema

from server.models import Player

User = get_user_model()


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
        model_fields = ["username", "first_name", "last_name"]


class UserFormSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["first_name", "last_name", "phone"]


class PlayerFormSchema(ModelSchema):
    class Config:
        model = Player
        model_exclude = ["user"]
        model_fields_optional = "__all__"


class RegistrationSchema(UserFormSchema, PlayerFormSchema):
    pass

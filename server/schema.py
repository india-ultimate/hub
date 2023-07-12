from typing import List

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


class PlayerSchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(player):
        return player.user.get_full_name()

    class Config:
        model = Player
        model_fields = "__all__"


class UserSchema(ModelSchema):
    player: PlayerSchema = None

    @staticmethod
    def resolve_player(user):
        try:
            return PlayerSchema.from_orm(user.player_profile)
        except Player.DoesNotExist:
            return

    players: List[PlayerSchema]

    @staticmethod
    def resolve_players(user):
        players = Player.objects.filter(guardianship__user=user)
        return [PlayerSchema.from_orm(p) for p in players]

    class Config:
        model = User
        model_fields = [
            "username",
            "email",
            "phone",
            "is_player",
            "is_guardian",
            "first_name",
            "last_name",
        ]


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

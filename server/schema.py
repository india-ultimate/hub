from typing import List

from django.contrib.auth import get_user_model
from ninja import ModelSchema, Schema

from server.models import Event, Guardianship, Membership, Player, Vaccination

User = get_user_model()


class Credentials(Schema):
    username: str
    password: str


class FirebaseCredentials(Schema):
    token: str
    uid: str


class Response(Schema):
    message: str


class MembershipSchema(ModelSchema):
    class Config:
        model = Membership
        model_fields = "__all__"


class AnnualMembershipSchema(Schema):
    player_id: int
    year: int


class EventMembershipSchema(Schema):
    player_id: int
    event_id: int


class PaymentFormSchema(Schema):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class OrderSchema(Schema):
    order_id: str
    amount: int
    currency: str
    receipt: str
    key: str
    name: str
    image: str
    description: str
    prefill: dict


class PlayerSchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(player):
        return player.user.get_full_name()

    email: str

    @staticmethod
    def resolve_email(player):
        return player.user.email

    phone: str

    @staticmethod
    def resolve_phone(player):
        return player.user.phone

    membership: MembershipSchema = None

    @staticmethod
    def resolve_membership(player):
        try:
            return MembershipSchema.from_orm(player.membership)
        except Membership.DoesNotExist:
            return

    guardian: int = None

    @staticmethod
    def resolve_guardian(player):
        try:
            guardianship = Guardianship.objects.get(player=player)
            return guardianship.user.id
        except Guardianship.DoesNotExist:
            return

    class Config:
        model = Player
        model_fields = "__all__"


class EventSchema(ModelSchema):
    class Config:
        model = Event
        model_fields = ["id", "title", "start_date", "end_date"]


class UserSchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(user):
        return user.get_full_name()

    player: PlayerSchema = None

    @staticmethod
    def resolve_player(user):
        try:
            return PlayerSchema.from_orm(user.player_profile)
        except Player.DoesNotExist:
            return

    wards: List[PlayerSchema]

    @staticmethod
    def resolve_wards(user):
        wards = Player.objects.filter(guardianship__user=user)
        return [PlayerSchema.from_orm(p) for p in wards]

    class Config:
        model = User
        model_fields = [
            "username",
            "email",
            "phone",
            "first_name",
            "last_name",
        ]


class VaccinationSchema(ModelSchema):
    class Config:
        model = Vaccination
        model_fields = "__all__"


class UserFormSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["first_name", "last_name", "phone"]


class UserOtherFormSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["first_name", "last_name", "phone", "email"]


class UserWardFormSchema(ModelSchema):
    email: str = None

    class Config:
        model = User
        model_fields = ["first_name", "last_name", "phone", "email"]


class PlayerFormSchema(ModelSchema):
    class Config:
        model = Player
        model_exclude = ["user"]
        model_fields_optional = "__all__"


class GuardianshipFormSchema(ModelSchema):
    class Config:
        model = Guardianship
        model_fields = ["relation"]


class VaccinationFormSchema(ModelSchema):
    class Config:
        model = Vaccination
        model_exclude = ["player"]


class RegistrationSchema(UserFormSchema, PlayerFormSchema):
    pass


class RegistrationOthersSchema(UserOtherFormSchema, PlayerFormSchema):
    pass


class RegistrationWardSchema(UserWardFormSchema, PlayerFormSchema, GuardianshipFormSchema):
    pass

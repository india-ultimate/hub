from typing import Any, Dict, List, Optional

from ninja import ModelSchema, Schema

from server.models import (
    Event,
    Guardianship,
    Membership,
    Player,
    RazorpayTransaction,
    User,
    Vaccination,
)
from server.utils import mask_string


class Credentials(Schema):
    username: str
    password: str


class FirebaseCredentials(Schema):
    token: str
    uid: str


class Response(Schema):
    message: str


class MembershipSchema(ModelSchema):
    waiver_signed_by: Optional[str]

    @staticmethod
    def resolve_waiver_signed_by(membership: Membership) -> Optional[str]:
        user = membership.waiver_signed_by
        return user.get_full_name() if user is not None else None

    class Config:
        model = Membership
        model_fields = "__all__"


class AnnualMembershipSchema(Schema):
    player_id: int
    year: int


class EventMembershipSchema(Schema):
    player_id: int
    event_id: int


class GroupMembershipSchema(Schema):
    player_ids: List[int]
    year: int


class PaymentFormSchema(Schema):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class EventSchema(ModelSchema):
    class Config:
        model = Event
        model_fields = ["id", "title", "start_date", "end_date"]


class TransactionSchema(ModelSchema):
    user: str

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> str:
        return transaction.user.get_full_name()

    players: List[str]

    @staticmethod
    def resolve_players(transaction: RazorpayTransaction) -> List[str]:
        return [p.user.get_full_name() for p in transaction.players.all()]

    event: Optional[EventSchema]

    @staticmethod
    def resolve_event(transaction: RazorpayTransaction) -> Optional[EventSchema]:
        if transaction.event is not None:
            return EventSchema.from_orm(transaction.event)
        return None

    class Config:
        model = RazorpayTransaction
        model_fields = "__all__"


class OrderSchema(Schema):
    order_id: str
    amount: int
    currency: str
    receipt: str
    key: str
    name: str
    image: str
    description: str
    prefill: Dict[str, Any]


class VaccinationSchema(ModelSchema):
    class Config:
        model = Vaccination
        model_fields = "__all__"


class PlayerSchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(player: Player) -> str:
        return player.user.get_full_name()

    email: str

    @staticmethod
    def resolve_email(player: Player) -> str:
        return player.user.email

    phone: str

    @staticmethod
    def resolve_phone(player: Player) -> str:
        return player.user.phone

    membership: Optional[MembershipSchema]

    @staticmethod
    def resolve_membership(player: Player) -> Optional[MembershipSchema]:
        try:
            return MembershipSchema.from_orm(player.membership)
        except Membership.DoesNotExist:
            return None

    vaccination: Optional[VaccinationSchema]

    @staticmethod
    def resolve_vaccination(player: Player) -> Optional[VaccinationSchema]:
        try:
            return VaccinationSchema.from_orm(player.vaccination)
        except Vaccination.DoesNotExist:
            return None

    guardian: Optional[int]

    @staticmethod
    def resolve_guardian(player: Player) -> Optional[int]:
        try:
            guardianship = Guardianship.objects.get(player=player)
            return guardianship.user.id
        except Guardianship.DoesNotExist:
            return None

    class Config:
        model = Player
        model_fields = "__all__"


class PlayerTinySchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(player: Player) -> str:
        return player.user.get_full_name()

    email: str

    @staticmethod
    def resolve_email(player: Player) -> str:
        username, suffix = (player.user.email.split("@") + [""])[:2]
        masked_username = mask_string(username)
        return f"{masked_username}@{suffix}"

    phone: str

    @staticmethod
    def resolve_phone(player: Player) -> str:
        return mask_string(player.user.phone)

    has_membership: bool

    @staticmethod
    def resolve_has_membership(player: Player) -> bool:
        try:
            return player.membership.is_active
        except Membership.DoesNotExist:
            return False

    class Config:
        model = Player
        model_fields = ["id", "city", "state_ut", "team_name", "educational_institution"]


class UserSchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(user: User) -> str:
        return user.get_full_name()

    player: Optional[PlayerSchema]

    @staticmethod
    def resolve_player(user: User) -> Optional[PlayerSchema]:
        try:
            return PlayerSchema.from_orm(user.player_profile)
        except Player.DoesNotExist:
            return None

    wards: List[PlayerSchema]

    @staticmethod
    def resolve_wards(user: User) -> List[PlayerSchema]:
        wards = Player.objects.filter(guardianship__user=user)
        return [PlayerSchema.from_orm(p) for p in wards]

    class Config:
        model = User
        model_fields = [
            "id",
            "username",
            "email",
            "phone",
            "first_name",
            "last_name",
        ]


class UserFormSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["first_name", "last_name", "phone"]


class UserOtherFormSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["first_name", "last_name", "phone", "email"]


class UserWardFormSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["first_name", "last_name", "phone", "email"]
        model_fields_optional = ["email"]


class PlayerFormSchema(ModelSchema):
    class Config:
        model = Player
        model_exclude = ["user"]
        model_fields_optional = "__all__"


class GuardianshipFormSchema(ModelSchema):
    class Config:
        model = Guardianship
        model_fields = ["relation"]


class NotVaccinatedFormSchema(Schema):
    player_id: int
    is_vaccinated: bool
    explain_not_vaccinated: str


class VaccinatedFormSchema(Schema):
    player_id: int
    is_vaccinated: bool
    name: str


class WaiverFormSchema(Schema):
    player_id: int


class RegistrationSchema(UserFormSchema, PlayerFormSchema):
    class Config:
        pass


class RegistrationOthersSchema(UserOtherFormSchema, PlayerFormSchema):
    class Config:
        pass


class RegistrationWardSchema(UserWardFormSchema, PlayerFormSchema, GuardianshipFormSchema):
    class Config:
        pass

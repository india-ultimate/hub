from typing import Any

from ninja import ModelSchema, Schema

from server.models import (
    Event,
    Guardianship,
    Membership,
    Player,
    RazorpayTransaction,
    Team,
    UCPerson,
    UCRegistration,
    User,
    Vaccination,
)
from server.utils import mask_string


class Credentials(Schema):
    username: str
    password: str


class TopScoreCredentials(Schema):
    username: str
    password: str
    player_id: int


class FirebaseCredentials(Schema):
    token: str
    uid: str
    login: bool


class FirebaseSignUpCredentials(Schema):
    token: str
    uid: str
    email: str
    first_name: str
    last_name: str
    phone: str
    sign_up: bool


class Response(Schema):
    message: str


class MembershipSchema(ModelSchema):
    waiver_signed_by: str | None

    @staticmethod
    def resolve_waiver_signed_by(membership: Membership) -> str | None:
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
    player_ids: list[int]
    year: int


class PaymentFormSchema(Schema):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class EventSchema(ModelSchema):
    class Config:
        model = Event
        model_fields = ["id", "title", "start_date", "end_date", "ultimate_central_slug"]


class TransactionSchema(ModelSchema):
    user: str

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> str:
        return transaction.user.get_full_name()

    players: list[str]

    @staticmethod
    def resolve_players(transaction: RazorpayTransaction) -> list[str]:
        return [p.user.get_full_name() for p in transaction.players.all()]

    event: EventSchema | None

    @staticmethod
    def resolve_event(transaction: RazorpayTransaction) -> EventSchema | None:
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
    prefill: dict[str, Any]


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

    membership: MembershipSchema | None

    @staticmethod
    def resolve_membership(player: Player) -> MembershipSchema | None:
        try:
            return MembershipSchema.from_orm(player.membership)
        except Membership.DoesNotExist:
            return None

    vaccination: VaccinationSchema | None

    @staticmethod
    def resolve_vaccination(player: Player) -> VaccinationSchema | None:
        try:
            return VaccinationSchema.from_orm(player.vaccination)
        except Vaccination.DoesNotExist:
            return None

    guardian: int | None

    @staticmethod
    def resolve_guardian(player: Player) -> int | None:
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
        username, suffix = ([*player.user.email.split("@"), ""])[:2]
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

    is_minor: bool

    class Config:
        model = Player
        model_fields = [
            "id",
            "city",
            "state_ut",
            "team_name",
            "educational_institution",
            "sponsored",
        ]


class TeamSchema(ModelSchema):
    class Config:
        model = Team
        model_fields = "__all__"


class PersonSchema(ModelSchema):
    player: PlayerSchema | None

    @staticmethod
    def resolve_player(person: UCPerson) -> Player | None:
        try:
            return Player.objects.get(ultimate_central_id=person.id)
        except Player.DoesNotExist:
            return None

    class Config:
        model = UCPerson
        model_fields = "__all__"


class UCRegistrationSchema(ModelSchema):
    team: TeamSchema
    person: PersonSchema

    class Config:
        model = UCRegistration
        model_fields = "__all__"


class UserSchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(user: User) -> str:
        return user.get_full_name()

    is_staff: bool

    @staticmethod
    def resolve_is_staff(user: User) -> bool:
        return user.is_staff

    player: PlayerSchema | None

    @staticmethod
    def resolve_player(user: User) -> PlayerSchema | None:
        try:
            return PlayerSchema.from_orm(user.player_profile)
        except Player.DoesNotExist:
            return None

    wards: list[PlayerSchema]

    @staticmethod
    def resolve_wards(user: User) -> list[PlayerSchema]:
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

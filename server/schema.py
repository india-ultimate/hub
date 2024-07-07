from typing import Any

from ninja import ModelSchema, Schema

from server.models import (
    Accreditation,
    Bracket,
    CollegeId,
    CommentaryInfo,
    CrossPool,
    Event,
    Guardianship,
    ManualTransaction,
    Match,
    MatchScore,
    Membership,
    PhonePeTransaction,
    Player,
    Pool,
    PositionPool,
    RazorpayTransaction,
    Registration,
    SpiritScore,
    Team,
    Tournament,
    TournamentField,
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


class OTPRequestCredentials(Schema):
    email: str


class OTPRequestResponse(Schema):
    otp_ts: int


class OTPLoginCredentials(Schema):
    email: str
    otp: str
    otp_ts: int


class Response(Schema):
    message: str


class ValidationStatsSchema(Schema):
    total: int
    invalid_found: int
    validated: int


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
        model_exclude = ["ultimate_central_id"]


class UserFormSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["first_name", "last_name", "phone"]


class ManualTransactionSchema(ModelSchema):
    user: UserFormSchema

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> User:
        return transaction.user

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
        model = ManualTransaction
        model_fields = "__all__"


class RazorpayTransactionSchema(ModelSchema):
    user: UserFormSchema

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> User:
        return transaction.user

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


class PhonePeTransactionSchema(ModelSchema):
    user: UserFormSchema

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> User:
        return transaction.user

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
        model = PhonePeTransaction
        model_fields = "__all__"


class ManualTransactionValidationFormSchema(Schema):
    transaction_id: str
    validation_comment: str


class ManualTransactionLiteSchema(ModelSchema):
    class Config:
        model = ManualTransaction
        model_fields = ["transaction_id", "amount", "currency"]


class PhonePePaymentSchema(Schema):
    redirect_url: str
    amount: int


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


class AccreditationSchema(ModelSchema):
    class Config:
        model = Accreditation
        model_fields = "__all__"


class CollegeIdSchema(ModelSchema):
    class Config:
        model = CollegeId
        model_fields = "__all__"


class CommentaryInfoSchema(ModelSchema):
    class Config:
        model = CommentaryInfo
        model_fields = "__all__"


class UserMinSchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(user: User) -> str:
        return user.get_full_name()

    class Config:
        model = User
        model_fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
        ]


class TeamSchema(ModelSchema):
    admins: list[UserMinSchema]

    class Config:
        model = Team
        model_fields = "__all__"


class TeamCreateSchema(Schema):
    name: str
    category: str
    state_ut: str
    city: str


class TeamUpdateSchema(Schema):
    id: str
    category: str | None
    state_ut: str | None
    city: str | None
    admin_ids: list[str] | None


class PersonTinySchema(ModelSchema):
    class Config:
        model = UCPerson
        model_fields = "__all__"


class PlayerSchema(ModelSchema):
    first_name: str

    @staticmethod
    def resolve_first_name(player: Player) -> str:
        return player.user.first_name

    last_name: str

    @staticmethod
    def resolve_last_name(player: Player) -> str:
        return player.user.last_name

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

    accreditation: AccreditationSchema | None

    @staticmethod
    def resolve_accreditation(player: Player) -> Accreditation | None:
        try:
            return player.accreditation
        except Accreditation.DoesNotExist:
            return None

    college_id: CollegeIdSchema | None

    @staticmethod
    def resolve_college_id(player: Player) -> CollegeId | None:
        try:
            return player.college_id
        except CollegeId.DoesNotExist:
            return None

    commentary_info: CommentaryInfoSchema | None

    @staticmethod
    def resolve_commentary_info(player: Player) -> CommentaryInfo | None:
        try:
            return player.commentary_info
        except CommentaryInfo.DoesNotExist:
            return None

    guardian: int | None

    @staticmethod
    def resolve_guardian(player: Player) -> int | None:
        try:
            guardianship = Guardianship.objects.get(player=player)
            return guardianship.user.id
        except Guardianship.DoesNotExist:
            return None

    teams: list[TeamSchema]

    uc_person: PersonTinySchema | None

    @staticmethod
    def resolve_uc_person(player: Player) -> UCPerson | None:
        if not player.ultimate_central_id:
            return None
        try:
            return UCPerson.objects.get(id=player.ultimate_central_id)
        except UCPerson.DoesNotExist:
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

    teams: list[TeamSchema]

    class Config:
        model = Player
        model_fields = [
            "id",
            "city",
            "state_ut",
            "teams",
            "educational_institution",
            "sponsored",
        ]


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

    admin_teams: list[TeamSchema]

    @staticmethod
    def resolve_admin_teams(user: User) -> list[TeamSchema]:
        return [TeamSchema.from_orm(team) for team in user.admin_teams.all()]

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
        model_exclude = ["user", "teams", "id", "ultimate_central_id"]
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


class AccreditationFormSchema(ModelSchema):
    player_id: int

    class Config:
        model = Accreditation
        model_fields = ["level", "date", "wfdf_id"]


class CollegeIdFormSchema(ModelSchema):
    player_id: int

    class Config:
        model = CollegeId
        model_fields = ["expiry"]


class CommentaryInfoFormSchema(ModelSchema):
    player_id: int

    class Config:
        model = CommentaryInfo
        model_fields = [
            "jersey_number",
            "ultimate_origin",
            "ultimate_attraction",
            "ultimate_fav_role",
            "ultimate_fav_exp",
            "interests",
            "fun_fact",
        ]


class WaiverFormSchema(Schema):
    player_id: int


class RegistrationSchema(UserFormSchema, PlayerFormSchema):
    player_id: int | None

    class Config:
        pass


class RegistrationGuardianSchema(RegistrationSchema, GuardianshipFormSchema):
    guardian_first_name: str
    guardian_last_name: str
    guardian_email: str
    guardian_phone: str

    class Config:
        pass


class RegistrationOthersSchema(UserOtherFormSchema, PlayerFormSchema):
    class Config:
        pass


class RegistrationWardSchema(UserWardFormSchema, PlayerFormSchema, GuardianshipFormSchema):
    class Config:
        pass


class TournamentSchema(ModelSchema):
    event: EventSchema
    teams: list[TeamSchema]

    class Config:
        model = Tournament
        model_fields = "__all__"


class TournamentCreateFromEventSchema(Schema):
    event_id: int


class TournamentCreateSchema(Schema):
    title: str
    start_date: str
    end_date: str
    registration_start_date: str
    registration_end_date: str
    location: str
    type: str


class TournamentUpdateSeedingSchema(Schema):
    seeding: dict[int, int]


class AddOrRemoveTeamRegistrationSchema(Schema):
    team_id: int


class AddToRosterSchema(Schema):
    player_id: int
    is_playing: bool
    role: str


class TournamentPlayerRegistrationUpdateSchema(Schema):
    role: str | None
    is_playing: bool | None


class TournamentPlayerRegistrationSchema(Schema):
    id: int
    team: TeamSchema
    player: PlayerSchema
    is_playing: bool
    role: str

    # @staticmethod
    # def resolve_role_full(registration: Registration) -> str:
    #     return Registration.Role._value2member_map_[registration.role]._label_  # type: ignore[attr-defined]

    class Config:
        model = Registration


class PoolSchema(ModelSchema):
    class Config:
        model = Pool
        model_exclude = ["tournament"]


class PoolCreateSchema(Schema):
    seeding: list[int]
    sequence_number: int
    name: str


class CrossPoolSchema(ModelSchema):
    class Config:
        model = CrossPool
        model_exclude = ["tournament"]


class BracketSchema(ModelSchema):
    class Config:
        model = Bracket
        model_exclude = ["tournament"]


class BracketCreateSchema(Schema):
    sequence_number: int
    name: str


class PositionPoolSchema(ModelSchema):
    class Config:
        model = PositionPool
        model_exclude = ["tournament"]


class PositionPoolCreateSchema(Schema):
    seeding: list[int]
    sequence_number: int
    name: str


class MatchScoreModelSchema(ModelSchema):
    entered_by: PlayerTinySchema

    class Config:
        model = MatchScore
        model_fields = "__all__"


class SpiritScoreSchema(ModelSchema):
    mvp: PersonSchema | None
    msp: PersonSchema | None

    class Config:
        model = SpiritScore
        model_fields = "__all__"


class TournamentFieldSchema(ModelSchema):
    class Config:
        model = TournamentField
        model_exclude = ["tournament"]


class TournamentFieldCreateSchema(Schema):
    name: str
    is_broadcasted: bool
    address: str | None


class TournamentFieldUpdateSchema(Schema):
    name: str | None
    is_broadcasted: bool | None
    tournament_id: int
    address: str | None


class MatchSchema(ModelSchema):
    pool: PoolSchema | None
    cross_pool: CrossPoolSchema | None
    bracket: BracketSchema | None
    position_pool: PositionPoolSchema | None
    team_1: TeamSchema | None
    team_2: TeamSchema | None
    spirit_score_team_1: SpiritScoreSchema | None
    spirit_score_team_2: SpiritScoreSchema | None
    self_spirit_score_team_1: SpiritScoreSchema | None
    self_spirit_score_team_2: SpiritScoreSchema | None
    suggested_score_team_1: MatchScoreModelSchema | None
    suggested_score_team_2: MatchScoreModelSchema | None
    field: TournamentFieldSchema | None

    class Config:
        model = Match
        model_exclude = ["tournament"]


class MatchCreateSchema(Schema):
    stage: str
    stage_id: int
    seq_num: int
    time: str
    field_id: int
    seed_1: int
    seed_2: int


class SpiritScoreUpdateSchema(Schema):
    rules: int
    fouls: int
    fair: int
    positive: int
    communication: int

    mvp_id: str | None
    msp_id: str | None

    comments: str | None


class SpiritScoreSubmitSchema(Schema):
    opponent: SpiritScoreUpdateSchema
    self: SpiritScoreUpdateSchema

    team_id: int


class MatchUpdateSchema(Schema):
    time: str | None
    field_id: int | None
    video_url: str | None
    duration_mins: int | None
    spirit_score_team_1: SpiritScoreUpdateSchema | None
    spirit_score_team_2: SpiritScoreUpdateSchema | None
    self_spirit_score_team_1: SpiritScoreUpdateSchema | None
    self_spirit_score_team_2: SpiritScoreUpdateSchema | None


class MatchScoreSchema(Schema):
    team_1_score: int
    team_2_score: int


class UserAccessSchema(Schema):
    is_staff: bool
    is_tournament_admin: bool
    playing_team_id: int
    admin_team_ids: list[int]


class TournamentRulesSchema(Schema):
    rules: str


class ContactFormSchema(Schema):
    subject: str
    description: str


class PasskeyResponseSchema(Schema):
    passkey_response: str


class PasskeyRequestSchema(Schema):
    passkey_request: str

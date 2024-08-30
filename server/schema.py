from ninja import ModelSchema, Schema

from server.core.models import (
    Accreditation,
    CollegeId,
    CommentaryInfo,
    Guardianship,
    Player,
    Team,
    UCPerson,
    User,
    Vaccination,
)
from server.membership.models import (
    Membership,
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
    description: str | None
    action_name: str | None
    action_href: str | None


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
    season_id: int


class EventMembershipSchema(Schema):
    player_id: int
    event_id: int


class GroupMembershipSchema(Schema):
    player_ids: list[int]
    season_id: int


class PaymentFormSchema(Schema):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class UserFormSchema(ModelSchema):
    class Config:
        model = User
        model_fields = ["first_name", "last_name", "phone"]


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


class TeamMinSchema(ModelSchema):
    class Config:
        model = Team
        model_fields = ["id", "name", "slug", "image", "image_url"]


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
        if not player.is_minor:
            return None
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
        return player.user.email

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


class PlayerMinSchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(player: Player) -> str:
        return player.user.get_full_name()

    class Config:
        model = Player
        model_fields = ["id", "state_ut", "match_up"]


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


class UserAccessSchema(Schema):
    is_staff: bool
    is_tournament_admin: bool
    playing_team_id: int
    admin_team_ids: list[int]
    is_tournament_volunteer: bool


class ContactFormSchema(Schema):
    subject: str
    description: str


class PasskeyResponseSchema(Schema):
    passkey_response: str


class PasskeyRequestSchema(Schema):
    passkey_request: str


class RegistrationCount(Schema):
    team_id: int
    count: int

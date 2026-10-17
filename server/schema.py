from typing import Any

from django.utils.timezone import now
from ninja import ModelSchema, Schema

from server.announcements.access import can_post
from server.constants import MIN_AGE
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
from server.duplicates.identity import mask_email
from server.payment_account.models import viewable_by
from server.season.models import Season
from server.subscription.models import Subscription
from server.subscription.schema import SubscriptionSchema
from server.subscription.sponsorship import has_grant
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
    description: str | None = None
    action_name: str | None = None
    action_href: str | None = None


class ValidationStatsSchema(Schema):
    total: int
    invalid_found: int
    validated: int


class UserFormSchema(ModelSchema):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone"]


class VaccinationSchema(ModelSchema):
    class Meta:
        model = Vaccination
        fields = "__all__"


class AccreditationSchema(ModelSchema):
    class Meta:
        model = Accreditation
        fields = "__all__"


class CollegeIdSchema(ModelSchema):
    # Empty once the images are removed after expiry (images_removed_at).
    card_front: str | None = None
    card_back: str | None = None

    class Meta:
        model = CollegeId
        fields = "__all__"


class CommentaryInfoSchema(ModelSchema):
    class Meta:
        model = CommentaryInfo
        fields = "__all__"


def viewer_is_staff(context: dict[str, Any] | None) -> bool:
    """For a resolver taking `context`: whether the request is a staff member's."""
    request = (context or {}).get("request")
    return bool(request is not None and request.user.is_staff)


def profile_pic_url(user: User) -> str | None:
    try:
        return user.player_profile.profile_pic_url
    except Exception:
        return None


class UserNameSchema(ModelSchema):
    """Someone named on a page, an author or an inviter: by name only."""

    full_name: str

    @staticmethod
    def resolve_full_name(user: User) -> str:
        return user.get_full_name()

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name"]


class UserSearchSchema(ModelSchema):
    """Someone a picker or a director list shows. The username, an email, is
    masked for all but staff."""

    full_name: str

    @staticmethod
    def resolve_full_name(user: User) -> str:
        return user.get_full_name()

    username: str

    @staticmethod
    def resolve_username(user: User, context: dict[str, Any]) -> str:
        return user.username if viewer_is_staff(context) else mask_email(user.username)

    class Meta:
        model = User
        fields = ["id"]


class TeamAdminSchema(ModelSchema):
    """An admin as anyone may see them: everything embedding a team is public."""

    full_name: str

    @staticmethod
    def resolve_full_name(user: User) -> str:
        return user.get_full_name()

    class Meta:
        model = User
        fields = ["id"]


class TeamSchema(ModelSchema):
    admins: list[TeamAdminSchema]

    class Meta:
        model = Team
        fields = "__all__"


class TeamMinSchema(ModelSchema):
    class Meta:
        model = Team
        fields = ["id", "name", "slug", "image", "image_url"]


class TeamCreateSchema(Schema):
    name: str
    category: str
    state_ut: str
    city: str


class TeamNameUpdateSchema(Schema):
    id: str
    name: str


class TeamUpdateSchema(Schema):
    id: str
    category: str | None = None
    state_ut: str | None = None
    city: str | None = None
    admin_ids: list[int] | None = None


class PersonTinySchema(ModelSchema):
    class Meta:
        model = UCPerson
        fields = "__all__"


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

    subscription: SubscriptionSchema | None = None

    @staticmethod
    def resolve_subscription(player: Player) -> Subscription | None:
        if hasattr(player, "_prefetched_subscription"):
            subscription = player._prefetched_subscription
        else:
            subscription = player.current_subscription
        return subscription

    sponsored: bool

    @staticmethod
    def resolve_sponsored(player: Player) -> bool:
        """A grant for the season this person would buy next.

        Computed, not the legacy `Player.sponsored` column: grants are per
        season now, and someone sponsored last season has to ask again.
        """
        if hasattr(player, "_prefetched_sponsored"):
            return bool(player._prefetched_sponsored)
        return has_grant(player, Season.current())

    vaccination: VaccinationSchema | None = None

    @staticmethod
    def resolve_vaccination(player: Player) -> Vaccination | None:
        try:
            return player.vaccination
        except Vaccination.DoesNotExist:
            return None

    accreditation: AccreditationSchema | None = None

    @staticmethod
    def resolve_accreditation(player: Player) -> Accreditation | None:
        try:
            return player.accreditation
        except Accreditation.DoesNotExist:
            return None

    college_id: CollegeIdSchema | None = None

    @staticmethod
    def resolve_college_id(player: Player) -> CollegeId | None:
        try:
            return player.college_id
        except CollegeId.DoesNotExist:
            return None

    commentary_info: CommentaryInfoSchema | None = None

    @staticmethod
    def resolve_commentary_info(player: Player) -> CommentaryInfo | None:
        try:
            return player.commentary_info
        except CommentaryInfo.DoesNotExist:
            return None

    guardian: int | None = None

    @staticmethod
    def resolve_guardian(player: Player) -> int | None:
        if not player.is_minor:
            return None
        try:
            guardianship = Guardianship.objects.get(player=player)
            return guardianship.user.id
        except Guardianship.DoesNotExist:
            return None

    teams: list[TeamMinSchema]

    uc_person: PersonTinySchema | None = None

    @staticmethod
    def resolve_uc_person(player: Player) -> UCPerson | None:
        if not player.ultimate_central_id:
            return None
        try:
            return UCPerson.objects.get(id=player.ultimate_central_id)
        except UCPerson.DoesNotExist:
            return None

    class Meta:
        model = Player
        fields = "__all__"


class PlayerTinySchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(player: Player) -> str:
        return player.user.get_full_name()

    email: str

    @staticmethod
    def resolve_email(player: Player) -> str:
        """Masked: enough for a picker to tell two namesakes apart."""
        return mask_email(player.user.email)

    phone: str

    @staticmethod
    def resolve_phone(player: Player) -> str:
        return mask_string(player.user.phone)

    has_subscription: bool

    @staticmethod
    def resolve_has_subscription(player: Player) -> bool:
        if hasattr(player, "_prefetched_subscription"):
            subscription = player._prefetched_subscription
        else:
            subscription = player.current_subscription
        return subscription is not None and subscription.is_active

    is_minor: bool

    teams: list[TeamMinSchema]

    class Meta:
        model = Player
        fields = [
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

    class Meta:
        model = Player
        fields = ["id", "state_ut", "match_up"]


class SubscriptionStatusSchema(ModelSchema):
    class Meta:
        model = Subscription
        fields = ["season", "is_active"]


class RosterPlayerSchema(ModelSchema):
    """A player as an admin of a team whose roster holds them sees them: what
    paying for their subscription needs, and none of their details."""

    full_name: str

    @staticmethod
    def resolve_full_name(player: Player) -> str:
        return player.user.get_full_name()

    is_minor: bool
    # Derived from the date of birth, which admins don't see: the subscription
    # page warns about it. The IU ID is a membership number, not contact data.
    under_min_age: bool

    @staticmethod
    def resolve_under_min_age(player: Player) -> bool:
        """Checked at the end of the season, as the subscription page checks it."""
        season = Season.current()
        return player.age_on(season.end_date if season else now().date()) < MIN_AGE

    teams: list[TeamMinSchema]
    subscription: SubscriptionStatusSchema | None = None

    @staticmethod
    def resolve_subscription(player: Player) -> Subscription | None:
        return player.current_subscription

    class Meta:
        model = Player
        fields = ["id", "iu_id", "teams"]


class PersonSchema(ModelSchema):
    player: PlayerSchema | None = None

    @staticmethod
    def resolve_player(person: UCPerson) -> Player | None:
        try:
            return Player.objects.get(ultimate_central_id=person.id)
        except Player.DoesNotExist:
            return None

    class Meta:
        model = UCPerson
        fields = "__all__"


class UserSchema(ModelSchema):
    full_name: str

    @staticmethod
    def resolve_full_name(user: User) -> str:
        return user.get_full_name()

    is_staff: bool

    @staticmethod
    def resolve_is_staff(user: User) -> bool:
        return user.is_staff

    directed_tournament_ids: list[int]

    @staticmethod
    def resolve_directed_tournament_ids(user: User) -> list[int]:
        return list(user.directed_tournaments.values_list("id", flat=True))

    player: PlayerSchema | None = None

    @staticmethod
    def resolve_player(user: User) -> Player | None:
        try:
            return user.player_profile
        except Player.DoesNotExist:
            return None

    wards: list[PlayerSchema]

    @staticmethod
    def resolve_wards(user: User) -> list[Player]:
        return list(Player.objects.filter(guardianship__user=user))

    admin_teams: list[TeamSchema]

    @staticmethod
    def resolve_admin_teams(user: User) -> list[Team]:
        return list(user.admin_teams.all())

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "phone",
            "first_name",
            "last_name",
        ]


class MeSchema(UserSchema):
    """The signed-in person's own user, for the frontend's user store. Not for nesting."""

    payment_accounts: list[dict[str, str]]
    can_post_announcements: bool

    @staticmethod
    def resolve_can_post_announcements(user: User) -> bool:
        return can_post(user)

    @staticmethod
    def resolve_payment_accounts(user: User) -> list[dict[str, str]]:
        return [{"slug": a.slug, "name": a.name} for a in viewable_by(user)]


class UserOtherFormSchema(ModelSchema):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "email"]


class UserWardFormSchema(ModelSchema):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "email"]
        fields_optional = ["email"]


class PlayerFormSchema(ModelSchema):
    class Meta:
        model = Player
        # sponsored decides what a subscription costs, imported_data says where
        # a row came from, and iu_id is printed on waivers and
        # certificates -- a self-chosen one is identity forgery. All three are
        # administrative and none may be set by the person registering, so
        # they are not input fields at all. The picture is set only by
        # uploading one, and the form doesn't send it: as a field here, every
        # profile edit would save it as empty.
        exclude = [
            "user",
            "teams",
            "id",
            "ultimate_central_id",
            "sponsored",
            "imported_data",
            "iu_id",
            "profile_pic_url",
        ]
        fields_optional = "__all__"


class GuardianshipFormSchema(ModelSchema):
    class Meta:
        model = Guardianship
        fields = ["relation"]


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

    class Meta:
        model = Accreditation
        fields = ["level", "date", "wfdf_id"]


class CollegeIdFormSchema(ModelSchema):
    player_id: int

    class Meta:
        model = CollegeId
        fields = ["expiry"]


class CommentaryInfoFormSchema(ModelSchema):
    player_id: int

    class Meta:
        model = CommentaryInfo
        fields = [
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


class CodeOfConductFormSchema(Schema):
    player_id: int


class RegistrationSchema(UserFormSchema, PlayerFormSchema):
    player_id: int | None = None

    # Each base has its own Meta; ninja reads none here (only on a direct
    # ModelSchema subclass), and this one settles which wins for mypy.
    class Meta:
        pass


class RegistrationGuardianSchema(RegistrationSchema, GuardianshipFormSchema):
    guardian_first_name: str
    guardian_last_name: str
    guardian_email: str
    guardian_phone: str

    # As in RegistrationSchema.
    class Meta:
        pass


class RegistrationOthersSchema(UserOtherFormSchema, PlayerFormSchema):
    # As in RegistrationSchema.
    class Meta:
        pass


class RegistrationWardSchema(UserWardFormSchema, PlayerFormSchema, GuardianshipFormSchema):
    # As in RegistrationSchema.
    class Meta:
        pass


class UserAccessSchema(Schema):
    is_staff: bool
    is_tournament_admin: bool
    is_tournament_director: bool
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

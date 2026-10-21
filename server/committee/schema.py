from datetime import date

from ninja import Field, Schema

from server.committee.models import Committee, Role
from server.core.models import User
from server.schema import profile_pic_url


class PersonSchema(Schema):
    id: int
    full_name: str
    profile_pic_url: str | None = None

    @staticmethod
    def resolve_full_name(user: User) -> str:
        return user.get_full_name()

    @staticmethod
    def resolve_profile_pic_url(user: User) -> str | None:
        return profile_pic_url(user)


class RoleSchema(Schema):
    id: int
    title: str
    is_chair: bool
    can_post_announcements: bool
    can_create_forms: bool
    start_date: date
    end_date: date | None = None
    person: PersonSchema

    @staticmethod
    def resolve_person(role: Role) -> User:
        return role.user


class CommitteeSchema(Schema):
    name: str
    slug: str
    email: str
    description: str
    order: int
    can_post_announcements: bool
    can_create_forms: bool
    roles: list[RoleSchema]

    @staticmethod
    def resolve_roles(committee: Committee) -> list[Role]:
        # Prefetched by the API, so a page of committees is not a query each
        return committee.current_roles  # type: ignore[attr-defined]


class CommitteeDetailSchema(CommitteeSchema):
    past_roles: list[RoleSchema]

    @staticmethod
    def resolve_past_roles(committee: Committee) -> list[Role]:
        past = committee.roles.past().select_related("user__player_profile")
        return list(past.order_by("-end_date", "-start_date", "id"))


class CommitteeInSchema(Schema):
    name: str
    email: str = ""
    description: str = ""
    order: int = Field(0, ge=0, le=32767)
    can_post_announcements: bool = False
    can_create_forms: bool = False


class RoleCreateSchema(Schema):
    user_id: int
    title: str
    is_chair: bool = False
    can_post_announcements: bool = False
    can_create_forms: bool = False
    start_date: date


class RoleUpdateSchema(Schema):
    title: str | None = None
    is_chair: bool | None = None
    can_post_announcements: bool | None = None
    can_create_forms: bool | None = None
    start_date: date | None = None
    end_date: date | None = None

from django.db import transaction
from django.db.models import Prefetch, Q, QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from ninja import Router

from server.committee.models import Committee, Role
from server.committee.schema import (
    CommitteeDetailSchema,
    CommitteeInSchema,
    CommitteeSchema,
    RoleCreateSchema,
    RoleSchema,
    RoleUpdateSchema,
)
from server.core.models import User

router = Router()

Message = dict[str, str]
# The staff page lives at /committees/manage, so no committee may take the slug
RESERVED_SLUG = "manage"


class AuthenticatedHttpRequest(HttpRequest):
    user: User


def _deny_unless_staff(user: User) -> tuple[int, Message] | None:
    if not user.is_staff:
        return 403, {"message": "Only staff can do this"}
    return None


def _committees() -> QuerySet[Committee]:
    """Every committee, with its current roles: chairs first, then by start date."""
    current = Role.objects.current().select_related("user__player_profile")
    return Committee.objects.prefetch_related(
        Prefetch(
            "roles", current.order_by("-is_chair", "start_date", "id"), to_attr="current_roles"
        )
    )


def _name_is_taken(name: str, committee: Committee | None = None) -> bool:
    taken = Committee.objects.filter(name=name)
    return taken.exclude(pk=committee.pk).exists() if committee else taken.exists()


def _save_unless_overlapping(role: Role) -> bool:
    """Save `role`, unless its term overlaps another of the same person's in the
    committee. Terms run from start_date up to, not including, end_date. The
    committee is locked, so two requests can't both pass the check, even for
    someone with no role in it yet."""
    with transaction.atomic():
        Committee.objects.select_for_update().get(pk=role.committee_id)
        others = Role.objects.filter(committee=role.committee, user=role.user)
        others = others.exclude(pk=role.pk).filter(
            Q(end_date__isnull=True) | Q(end_date__gt=role.start_date)
        )
        if role.end_date:
            others = others.filter(start_date__lt=role.end_date)
        if others.exists():
            return False
        role.save()
    return True


@router.get("/", auth=None, response={200: list[CommitteeSchema]})
def list_committees(request: HttpRequest) -> QuerySet[Committee]:
    """Every committee with who holds a role in it today. No login needed."""
    return _committees()


@router.get("/{slug}", auth=None, response={200: CommitteeDetailSchema, 404: Message})
def get_committee(request: HttpRequest, slug: str) -> Committee | tuple[int, Message]:
    """One committee, with its current people and its past ones."""
    committee = _committees().filter(slug=slug).first()
    return committee or (404, {"message": "Committee not found"})


@router.post("/", response={201: CommitteeSchema, 400: Message, 403: Message})
def create_committee(
    request: AuthenticatedHttpRequest, data: CommitteeInSchema
) -> tuple[int, Committee | Message]:
    if denied := _deny_unless_staff(request.user):
        return denied
    slug = slugify(data.name)
    if not slug:
        return 400, {"message": "The name needs letters or digits"}
    if slug == RESERVED_SLUG:
        return 400, {"message": f'"{RESERVED_SLUG}" is reserved, pick another name'}
    if _name_is_taken(data.name) or Committee.objects.filter(slug=slug).exists():
        return 400, {"message": "A committee with this name already exists"}
    committee = Committee.objects.create(slug=slug, **data.dict())
    return 201, _committees().get(pk=committee.pk)


@router.put("/{slug}", response={200: CommitteeSchema, 400: Message, 403: Message, 404: Message})
def update_committee(
    request: AuthenticatedHttpRequest, slug: str, data: CommitteeInSchema
) -> tuple[int, Committee | Message]:
    if denied := _deny_unless_staff(request.user):
        return denied
    committee = Committee.objects.filter(slug=slug).first()
    if not committee:
        return 404, {"message": "Committee not found"}
    if _name_is_taken(data.name, committee):
        return 400, {"message": "A committee with this name already exists"}
    for field, value in data.dict().items():
        setattr(committee, field, value)
    committee.save()
    return 200, _committees().get(pk=committee.pk)


@router.post("/{slug}/roles", response={201: RoleSchema, 400: Message, 403: Message, 404: Message})
def add_role(
    request: AuthenticatedHttpRequest, slug: str, data: RoleCreateSchema
) -> tuple[int, Role | Message]:
    if denied := _deny_unless_staff(request.user):
        return denied
    committee = get_object_or_404(Committee, slug=slug)
    user = get_object_or_404(User, id=data.user_id)
    role = Role(
        committee=committee,
        user=user,
        title=data.title,
        is_chair=data.is_chair,
        start_date=data.start_date,
    )
    if not _save_unless_overlapping(role):
        return 400, {"message": "Their term overlaps another in this committee"}
    return 201, role


@router.put(
    "/roles/{role_id}", response={200: RoleSchema, 400: Message, 403: Message, 404: Message}
)
def update_role(
    request: AuthenticatedHttpRequest, role_id: int, data: RoleUpdateSchema
) -> tuple[int, Role | Message]:
    """Change a role. Ending a term is setting its end_date."""
    if denied := _deny_unless_staff(request.user):
        return denied
    role = get_object_or_404(Role, id=role_id)
    changes = data.dict(exclude_unset=True)
    # Clearing end_date reopens a term; nothing else can be cleared.
    if any(value is None for field, value in changes.items() if field != "end_date"):
        return 400, {"message": "Only the end date can be cleared"}
    for field, value in changes.items():
        setattr(role, field, value)
    if role.end_date and role.end_date < role.start_date:
        return 400, {"message": "A term can't end before it starts"}
    if not _save_unless_overlapping(role):
        return 400, {"message": "Their term overlaps another in this committee"}
    return 200, role


@router.delete("/roles/{role_id}", response={204: None, 403: Message, 404: Message})
def delete_role(request: AuthenticatedHttpRequest, role_id: int) -> tuple[int, Message | None]:
    """For a role added by mistake. An ended term is kept as the archive."""
    if denied := _deny_unless_staff(request.user):
        return denied
    get_object_or_404(Role, id=role_id).delete()
    return 204, None

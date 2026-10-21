"""Who may create forms, and manage the ones they made."""

from django.db.models import Q

from server.committee.models import Role
from server.core.models import User
from server.forms.models import Form


def can_create_forms(user: User) -> bool:
    """Staff, and anyone with a current role that lets them: the role's own switch,
    or the committee's. Access ends with the term."""
    if user.is_staff:
        return True
    allowed = Q(can_create_forms=True) | Q(committee__can_create_forms=True)
    return Role.objects.current().filter(allowed, user=user).exists()


def can_manage_form(user: User, form: Form) -> bool:
    """Staff manage every form; a creator, the ones they made."""
    return user.is_staff or (form.created_by_id == user.id and can_create_forms(user))

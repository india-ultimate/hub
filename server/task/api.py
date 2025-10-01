from django.http import HttpRequest
from ninja import Router

from server.core.models import User
from server.task.manager import TaskManager

router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


@router.get("/status/", response={200: dict[str, int], 403: dict[str, str]})
def get_task_queue_status(
    request: AuthenticatedHttpRequest,
) -> dict[str, int] | tuple[int, dict[str, str]]:
    """Get the status of the task queue"""
    if not request.user.is_staff:
        return 403, {"message": "Only staff members can perform this action"}

    return TaskManager.get_task_stats()

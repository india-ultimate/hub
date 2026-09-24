"""Staff requests for merging an account whose inbox is gone."""

from server.servicerequests.models import ServiceRequest, ServiceRequestStatus


def close_request(request: ServiceRequest, note: str) -> None:
    """End a merge request nobody needs to decide any more.

    Rejected, because the status has no "withdrawn"; the note says why. The
    approval signal sends nothing for this type, so this is silent.
    """
    if request.status != ServiceRequestStatus.PENDING:
        return
    request.status = ServiceRequestStatus.REJECTED
    request.message = f"{request.message}\n\n[{note}]"
    request.save(update_fields=["status", "message", "updated_at"])

from server.core.models import Player, User
from server.season.models import Season
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus
from server.subscription import sponsorship


def approve_sponsorship(item: ServiceRequest, by: User) -> tuple[Season | None, list[Player]]:
    """Grant the season to each requested player, then mark the request approved.

    Granted before the status is saved, so the grant records who approved it:
    the status signal grants too, and whichever runs first wins. It also covers
    a request created already approved, whose players the signal cannot see.
    """
    season = item.season or Season.current()
    if season is None:
        return None, []
    players = list(item.service_players.all())
    for player in players:
        sponsorship.grant(player, season, by=by, request=item)
    if item.status != ServiceRequestStatus.APPROVED:
        item.status = ServiceRequestStatus.APPROVED
        item.save()
    return season, players


def reject(item: ServiceRequest) -> None:
    item.status = ServiceRequestStatus.REJECTED
    item.save()

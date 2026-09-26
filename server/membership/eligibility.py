"""Whether a person may be rostered, and in what role."""

from server.core.models import Player
from server.membership.models import Membership, MembershipTypeScope, Scope
from server.season.models import Season
from server.series.models import Series
from server.tournament.models import Event
from server.types import message_response


def _needs_membership(target: Event | Series) -> bool:
    """A series always counts. A one-off event counts if staff said so."""
    if isinstance(target, Series):
        return True
    return target.series_id is not None or target.is_membership_needed


def _season_of(target: Event | Series) -> Season | None:
    """The series' season; failing that, the season the target starts in."""
    series: Series | None = None
    if isinstance(target, Series):
        series = target
    elif target.series_id is not None:
        series = target.series
    if series is not None and series.season is not None:
        return series.season
    return Season.containing(target.start_date)


def _tiers_allowing(scope: str) -> str:
    """The tiers granting a scope, in catalog order: "Patron, Regular or Discounted"."""
    names = list(
        MembershipTypeScope.objects.filter(scope=scope)
        .order_by("type__display_order", "type__name")
        .values_list("type__name", flat=True)
    )
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} or {names[-1]}"


def check(player: Player, target: Event | Series, is_playing: bool) -> message_response | None:
    """None if this person may be rostered here, otherwise why not."""
    if not _needs_membership(target):
        return None

    season = _season_of(target)
    if season is None:
        return {
            "message": "No season for this event",
            "description": (
                "This event's dates fall outside every season, so membership "
                "cannot be checked. Ask an admin to add the season."
            ),
        }

    membership = Membership.objects.filter(player=player).for_season(season).first()
    if membership is None or not membership.is_active:
        return {
            "message": "Membership missing",
            "description": (
                f"You need an active India Ultimate membership for {season.name} "
                "to be added here."
            ),
            "action_name": "Get membership",
            "action_href": f"/membership/{player.id}",
        }

    if not membership.waiver_valid:
        return {
            "message": "Waiver not signed",
            "description": "You need to sign the liability waiver to be added here.",
            "action_name": "Sign waiver",
            "action_href": f"/waiver/{player.id}",
        }

    scope = Scope.PLAY_CHAMPIONSHIPS if is_playing else Scope.STAFF_CHAMPIONSHIPS
    if not membership.allows(scope):
        # Tier names already say "membership", e.g. "Community Membership".
        held = membership.plan.type.name if membership.plan is not None else "Your membership"
        doing = "playing" if is_playing else "coaching or managing"
        return {
            "message": f"Membership does not cover {doing} here",
            "description": (
                f"{held} does not cover {doing} here. "
                f"{doing.capitalize()} needs {_tiers_allowing(scope)}."
            ),
            "action_name": "Upgrade membership" if is_playing else "Change membership",
            "action_href": f"/membership/{player.id}",
        }

    return None

"""Whether a person may be rostered, and in what role."""

from server.core.models import Player
from server.season.models import Season
from server.series.models import Series
from server.subscription.models import Scope, Subscription, SubscriptionTypeScope
from server.tournament.models import Event
from server.types import message_response


def _needs_subscription(target: Event | Series) -> bool:
    """A series always counts. A one-off event counts if staff said so."""
    if isinstance(target, Series):
        return True
    return target.series_id is not None or target.is_subscription_needed


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
        SubscriptionTypeScope.objects.filter(scope=scope)
        .order_by("type__display_order", "type__name")
        .values_list("type__name", flat=True)
    )
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} or {names[-1]}"


def check(player: Player, target: Event | Series, is_playing: bool) -> message_response | None:
    """None if this person may be rostered here, otherwise why not."""
    if not _needs_subscription(target):
        return None

    season = _season_of(target)
    if season is None:
        return {
            "message": "No season for this event",
            "description": (
                "This event's dates fall outside every season, so subscription "
                "cannot be checked. Ask an admin to add the season."
            ),
        }

    subscription = Subscription.objects.filter(player=player).for_season(season).first()
    if subscription is None or not subscription.is_active:
        return {
            "message": "Subscription missing",
            "description": (
                f"You need an active India Ultimate subscription for {season.name} "
                "to be added here."
            ),
            "action_name": "Get subscription",
            "action_href": f"/subscription/{player.id}",
        }

    if not subscription.waiver_valid:
        return {
            "message": "Waiver not signed",
            "description": "You need to sign the liability waiver to be added here.",
            "action_name": "Sign waiver",
            "action_href": f"/waiver/{player.id}",
        }

    scope = Scope.PLAY_CHAMPIONSHIPS if is_playing else Scope.STAFF_CHAMPIONSHIPS
    if not subscription.allows(scope):
        # Tier names already say "subscription", e.g. "Community Subscription".
        held = subscription.plan.type.name if subscription.plan is not None else "Your subscription"
        doing = "playing" if is_playing else "coaching or managing"
        return {
            "message": f"Subscription does not cover {doing} here",
            "description": (
                f"{held} does not cover {doing} here. "
                f"{doing.capitalize()} needs {_tiers_allowing(scope)}."
            ),
            "action_name": "Upgrade subscription" if is_playing else "Change subscription",
            "action_href": f"/subscription/{player.id}",
        }

    return None

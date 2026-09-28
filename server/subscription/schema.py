"""The subscription shapes the API returns."""

from ninja import ModelSchema, Schema

from server.subscription.models import LEGACY_SCOPES, Subscription, SubscriptionTypeScope


class SubscriptionPlanSchema(Schema):
    id: int
    slug: str
    name: str
    description: str
    amount: int
    requires_grant: bool
    available_to_player: bool
    upgrade_from: str | None = None
    upgrade_amount: int | None = None


class SubscriptionSchema(ModelSchema):
    waiver_signed_by: str | None
    tier: str | None
    scopes: list[str]

    @staticmethod
    def resolve_waiver_signed_by(subscription: Subscription) -> str | None:
        user = subscription.waiver_signed_by
        return user.get_full_name() if user is not None else None

    @staticmethod
    def resolve_tier(subscription: Subscription) -> str | None:
        return subscription.tier

    @staticmethod
    def resolve_scopes(subscription: Subscription) -> list[str]:
        """What this subscription lets its holder do.

        No plan means the row predates the catalog, when every subscription was
        a full one. The forward query sidesteps the django-stubs quirk that
        can't see `type.scopes` from here.
        """
        if subscription.plan is None:
            return sorted(LEGACY_SCOPES)
        return sorted(
            SubscriptionTypeScope.objects.filter(type=subscription.plan.type).values_list(
                "scope", flat=True
            )
        )

    class Config:
        model = Subscription
        # subscription_number and is_annual are retained on the model only
        # for the deploy window (a still-running previous release reads
        # the columns); they are not part of this API. Exclude rather than
        # enumerate, so fields later tasks add (plan, amount_paid,
        # refunded_at, ...) keep appearing here automatically.
        model_exclude = ["subscription_number", "is_annual"]

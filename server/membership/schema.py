"""The membership shapes the API returns."""

from ninja import ModelSchema, Schema

from server.membership.models import LEGACY_SCOPES, Membership, MembershipTypeScope


class MembershipPlanSchema(Schema):
    id: int
    slug: str
    name: str
    description: str
    amount: int
    requires_grant: bool
    available_to_player: bool
    upgrade_from: str | None = None
    upgrade_amount: int | None = None


class MembershipSchema(ModelSchema):
    waiver_signed_by: str | None
    tier: str | None
    tier_name: str | None
    scopes: list[str]
    season_name: str

    @staticmethod
    def resolve_tier_name(membership: Membership) -> str | None:
        """The tier as people read it; `tier` is the slug code compares."""
        return membership.plan.type.name if membership.plan is not None else None

    @staticmethod
    def resolve_season_name(membership: Membership) -> str:
        """The season spelled out, so a history list reads without a lookup."""
        return membership.season.name

    @staticmethod
    def resolve_waiver_signed_by(membership: Membership) -> str | None:
        user = membership.waiver_signed_by
        return user.get_full_name() if user is not None else None

    @staticmethod
    def resolve_tier(membership: Membership) -> str | None:
        return membership.tier

    @staticmethod
    def resolve_scopes(membership: Membership) -> list[str]:
        """What this membership lets its holder do.

        No plan means the row predates the catalog, when every membership was
        a full one. The forward query sidesteps the django-stubs quirk that
        can't see `type.scopes` from here.
        """
        if membership.plan is None:
            return sorted(LEGACY_SCOPES)
        return sorted(
            MembershipTypeScope.objects.filter(type=membership.plan.type).values_list(
                "scope", flat=True
            )
        )

    class Config:
        model = Membership
        # membership_number and is_annual are retained on the model only
        # for the deploy window (a still-running previous release reads
        # the columns); they are not part of this API. Exclude rather than
        # enumerate, so fields later tasks add (plan, amount_paid,
        # refunded_at, ...) keep appearing here automatically.
        model_exclude = ["membership_number", "is_annual"]

"""Give orders placed before this change a tier, so a late payment still lands.

An order sitting unpaid at deploy time has a link row with no plan. Without
this, the payment completes and fulfil skips it.
"""

from typing import Any

from django.db import migrations

# What the old checkout charged, by season name.
OLD_PRICES = {
    "Season 2026-2027": {150000: "patron", 75000: "regular", 25000: "discounted"},
}


def fill_pending_lines(apps: Any, schema_editor: Any) -> None:
    MembershipPlan = apps.get_model("server", "MembershipPlan")  # noqa: N806
    RazorpayTransaction = apps.get_model("server", "RazorpayTransaction")  # noqa: N806
    RazorpayTransactionPlayer = apps.get_model("server", "RazorpayTransactionPlayer")  # noqa: N806

    plans = {
        (plan.season.name, plan.type.slug): plan
        for plan in MembershipPlan.objects.select_related("season", "type")
    }

    # Abandoned orders are in here too — production has 927 of them. Giving
    # them a tier costs nothing: they only matter if one is ever paid.
    pending = (
        RazorpayTransaction.objects.filter(type="annual-membership", season__isnull=False)
        .exclude(status="completed")
        .select_related("season")
    )

    for transaction in pending:
        prices = OLD_PRICES.get(transaction.season.name)
        if not prices:
            continue
        lines = RazorpayTransactionPlayer.objects.filter(transaction=transaction).select_related(
            "player"
        )
        if lines.count() != 1:
            # Only a single-person order can be read back with certainty. The
            # amount is what was charged when the order was placed, while the
            # line set is what it is now, so dividing one by the other can
            # land dead on another tier's price and quietly sell the wrong
            # tier. These orders are unpaid; no tier is better than a wrong
            # one, and staff see the line.
            continue
        line = lines.first()
        if line.plan_id is not None:
            continue
        slug = prices.get(transaction.amount)
        if slug is None:
            # Nothing the old checkout charged one person. Leave it; fulfil
            # skips it and the line shows up for staff.
            continue
        plan = plans.get((transaction.season.name, slug))
        if plan is None:
            continue
        # The discounted rate was gated on Player.sponsored before grants
        # existed, so respect what that said at the time.
        if slug == "discounted" and not line.player.sponsored:
            continue
        line.plan = plan
        line.amount = transaction.amount
        line.save(update_fields=["plan", "amount"])


def noop(apps: Any, schema_editor: Any) -> None:
    pass


class Migration(migrations.Migration):
    dependencies = [("server", "0154_refunds")]
    operations = [migrations.RunPython(fill_pending_lines, noop)]

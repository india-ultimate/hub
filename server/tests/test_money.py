"""Money is stored in paise and read and typed as rupees, the same way everywhere."""

import json
import re
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from server.admin import RupeeField, export_as_csv
from server.core.models import User
from server.receipts.money import rupees
from server.season.models import Season
from server.subscription.models import SubscriptionPlan
from server.tournament.models import Event
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer

from .test_admin_pickers import AdminPageCase
from .test_subscription_model import make_player

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"

# Every money column, all in paise. The first five predate "in paise" help text.
MONEY = {
    ("Event", "team_fee"),
    ("Event", "player_fee"),
    ("Event", "partial_team_fee"),
    ("Event", "team_late_penalty"),
    ("Event", "player_late_penalty"),
    ("Season", "annual_subscription_amount"),
    ("Season", "sponsored_annual_subscription_amount"),
    ("Season", "supporter_annual_subscription_amount"),
    ("SubscriptionPlan", "amount"),
    ("Subscription", "amount_paid"),
    ("Form", "payment_amount"),
    ("RazorpayTransaction", "amount"),
    ("RazorpayTransactionPlayer", "amount"),
    ("RazorpayRefund", "amount"),
    ("Receipt", "total"),
    ("PhonePeTransaction", "amount"),
    ("ManualTransaction", "amount"),
}


class TestRupees(SimpleTestCase):
    def test_whole_rupees_drop_the_paise(self) -> None:
        self.assertEqual("₹0", rupees(0))
        self.assertEqual("₹750", rupees(75000))
        self.assertEqual("₹7,500", rupees(750000))

    def test_paise_are_shown_when_there_are_some(self) -> None:
        self.assertEqual("₹749.50", rupees(74950))
        self.assertEqual("₹0.05", rupees(5))

    def test_indian_grouping(self) -> None:
        self.assertEqual("₹1,00,000", rupees(10000000))
        self.assertEqual("₹1,23,45,678.90", rupees(1234567890))

    def test_negative(self) -> None:
        self.assertEqual("-₹749.50", rupees(-74950))


class TestRupeeField(SimpleTestCase):
    def test_typed_rupees_are_stored_as_paise(self) -> None:
        field = RupeeField()
        self.assertEqual(75000, field.clean("750"))
        self.assertEqual(74950, field.clean("749.50"))
        self.assertEqual(5, field.clean("0.05"))

    def test_stored_paise_open_as_rupees(self) -> None:
        field = RupeeField()
        self.assertEqual("750", field.prepare_value(75000))
        self.assertEqual("749.50", field.prepare_value(74950))
        # What was typed comes back as typed, valid or not.
        self.assertEqual("7.5", field.prepare_value("7.5"))

    def test_refuses_fractions_of_a_paisa_and_negatives(self) -> None:
        field = RupeeField()
        with self.assertRaises(forms.ValidationError):
            field.clean("749.505")
        with self.assertRaises(forms.ValidationError):
            field.clean("-1")

    def test_refuses_more_than_the_column_holds(self) -> None:
        self.assertEqual(2147483647, RupeeField().clean("21474836.47"))
        with self.assertRaises(forms.ValidationError):
            RupeeField().clean("21474836.48")

    def test_optional_blank_is_none(self) -> None:
        self.assertIsNone(RupeeField(required=False).clean(""))

    def test_unchanged_value_is_not_a_change(self) -> None:
        field = RupeeField()
        self.assertFalse(field.has_changed(75000, "750"))
        self.assertFalse(field.has_changed(75000, "750.00"))
        self.assertTrue(field.has_changed(75000, "751"))


def _request() -> Any:
    request = RequestFactory().get("/admin/")
    request.user = User(is_superuser=True, is_staff=True, is_active=True)
    return request


class TestAdminSpeaksRupees(SimpleTestCase):
    def admins(self) -> list[tuple[Any, Any]]:
        request = _request()
        found: list[tuple[Any, Any]] = []
        for model, model_admin in admin.site._registry.items():
            found.append((model, model_admin))
            for inline in model_admin.get_inline_instances(request):
                found.append((inline.model, inline))
        return found

    def test_every_money_form_field_takes_rupees(self) -> None:
        request = _request()
        plain = []
        for model, model_admin in self.admins():
            if isinstance(model_admin, admin.options.InlineModelAdmin):
                form = model_admin.get_formset(request).form
            else:
                form = model_admin.get_form(request)
            for name, field in form.base_fields.items():
                if (model.__name__, name) in MONEY and not isinstance(field, RupeeField):
                    plain.append(f"{model.__name__}.{name}")
        self.assertEqual([], plain)

    def test_no_list_or_read_only_page_shows_raw_paise(self) -> None:
        request = _request()
        raw = []
        for model, model_admin in self.admins():
            # An existing object's page: inlines are judged on their parent's.
            parent = getattr(model_admin, "parent_model", model)
            obj = parent()
            shown = list(getattr(model_admin, "list_display", ()))
            readonly = list(model_admin.get_readonly_fields(request, obj))
            shown += readonly
            if not model_admin.has_change_permission(request, obj):
                # Nothing on the page is editable, so every field is shown as is.
                shown += [f for f in model_admin.get_fields(request, obj) if f not in readonly]
            raw += [f"{model.__name__}.{f}" for f in shown if (model.__name__, f) in MONEY]
        self.assertEqual([], sorted(set(raw)))


class TestStaffWithoutChangeRights(AdminPageCase):
    """Staff who may only look see rupees too, and nothing goes missing."""

    def setUp(self) -> None:
        super().setUp()
        self.viewer = User.objects.create(
            username="viewer@example.com", email="viewer@example.com", is_staff=True
        )
        self.client.force_login(self.viewer)

    def grant(self, *codenames: str) -> None:
        self.viewer.user_permissions.add(*Permission.objects.filter(codename__in=codenames))

    def test_view_only_order_page_shows_rupees(self) -> None:
        self.grant("view_razorpaytransaction", "view_razorpaytransactionplayer")
        player = make_player("viewed@example.com")
        order = RazorpayTransaction.objects.create(
            order_id="order_viewed", amount=74950, currency="INR", user=player.user
        )
        RazorpayTransactionPlayer.objects.create(transaction=order, player=player, amount=12345)
        page = self.client.get(
            reverse("admin:server_razorpaytransaction_change", args=[order.pk])
        ).content.decode()
        self.assertIn("₹749.50", page)
        self.assertIn("₹123.45", page)
        self.assertNotIn("74950", page)
        self.assertNotIn(">12345<", page)

    def test_order_add_page_for_staff_who_cannot_change_lines(self) -> None:
        self.grant(
            "add_razorpaytransaction",
            "view_razorpaytransaction",
            "add_razorpaytransactionplayer",
            "view_razorpaytransactionplayer",
        )
        page = self.client.get(reverse("admin:server_razorpaytransaction_add"))
        self.assertEqual(200, page.status_code)

    def test_add_only_staff_still_get_the_rupee_input(self) -> None:
        self.grant("add_form", "view_form")
        page = self.client.get(reverse("admin:server_form_add")).content.decode()
        self.assertIn('name="payment_amount"', page)


class TestAdminRoundTrip(AdminPageCase):
    def test_plan_price_opens_and_saves_in_rupees(self) -> None:
        plan = SubscriptionPlan.objects.get(
            season=Season.objects.get(name="Season 2026-2027"), type__slug="regular"
        )
        plan.amount = 74950
        plan.save()
        model_admin = admin.site._registry[SubscriptionPlan]
        request = _request()
        plan_form = model_admin.get_form(request, plan)
        self.assertEqual("749.50", plan_form(instance=plan)["amount"].value())
        data = {f: getattr(plan, f + "_id", getattr(plan, f, "")) for f in plan_form.base_fields}
        data.update(amount="800", is_available="on" if plan.is_available else "")
        form = plan_form(data=data, instance=plan)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        plan.refresh_from_db()
        self.assertEqual(80000, plan.amount)

    def test_event_fee_label_says_rupees(self) -> None:
        event_form = admin.site._registry[Event].get_form(_request())
        self.assertIn("(₹)", str(event_form.base_fields["team_fee"].label))

    def test_order_list_shows_rupees(self) -> None:
        user = make_player("payer@example.com").user
        RazorpayTransaction.objects.create(
            order_id="order_rupees", amount=1234550, currency="INR", user=user
        )
        page = self.client.get(reverse("admin:server_razorpaytransaction_changelist"))
        self.assertContains(page, "₹12,345.50")

    def test_csv_export_is_in_rupees(self) -> None:
        user = make_player("csv@example.com").user
        RazorpayTransaction.objects.create(
            order_id="order_csv", amount=74950, currency="INR", user=user
        )
        model_admin = admin.site._registry[RazorpayTransaction]
        response = export_as_csv(model_admin, _request(), RazorpayTransaction.objects.all())
        header, row = response.content.decode().splitlines()[:2]
        columns = header.split(",")
        self.assertIn("amount (₹)", columns)
        self.assertEqual("749.50", row.split(",")[columns.index("amount (₹)")])


# Only money.js turns paise into rupees and back. Anything else that divides
# or multiplies by 100 must be listed here as not being money.
NOT_MONEY = {
    ("utils.js", "length * 100"),  # a percentage
    ("components/ValidateRoster.js", "status / 100"),  # an HTTP status class
    ("components/ValidateRoster.js", "age * 100) / 100"),  # an age to 2 places
}
BY_100 = re.compile(r"[/*]\s*100\b")
MONEY_WORDS = re.compile(r"amount|fee|paise|price|total|rupee|penalty|₹|collected|refund", re.I)


class TestFrontendConvertsInOnePlace(SimpleTestCase):
    def test_no_money_conversion_outside_money_js(self) -> None:
        stray = []
        for path in FRONTEND.rglob("*.js"):
            name = str(path.relative_to(FRONTEND))
            if name == "money.js":
                continue
            for number, line in enumerate(path.read_text().splitlines(), 1):
                by_100 = BY_100.search(line) and not any(
                    name == file and snippet in line for file, snippet in NOT_MONEY
                )
                formats_money = "toLocaleString(" in line and MONEY_WORDS.search(line)
                if by_100 or formats_money:
                    stray.append(f"{name}:{number}: {line.strip()}")
        self.assertEqual([], stray)

    def test_money_js(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not installed")
        script = (
            "import('"
            + (FRONTEND / "money.js").as_uri()
            + "').then(m => console.log(JSON.stringify(["
            "m.inr(0), m.inr(75000), m.inr(74950), m.inr(10000000), m.inr(5), m.inr(-74950),"
            "m.toPaise('749.50'), m.toPaise(750), m.toPaise('0.1'), m.toRupees(74950)])))"
        )
        command = [node, "--input-type=module", "-e", script]
        # A fixed script run by the local node.
        out = subprocess.run(
            command,  # noqa: S603
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            ["₹0", "₹750", "₹749.50", "₹1,00,000", "₹0.05", "-₹749.50", 74950, 75000, 10, 749.5],
            json.loads(out.stdout),
        )


class TestDecimalSanity(TestCase):
    def test_no_float_drift(self) -> None:
        # 0.29 * 100 is 28.999999999999996 in floats; paise must come out exact.
        self.assertEqual(29, RupeeField().clean("0.29"))
        self.assertEqual(Decimal("0.29"), Decimal(29) / 100)

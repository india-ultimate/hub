"""Admin forms pick people and orders by search, never from a whole-table list.

A plain dropdown of players runs a query per option (a player's name reads
its user), so one such field on a form cost ~4,000 queries in production.
"""

import uuid
import warnings
from typing import Any

from django.contrib import admin
from django.contrib.admin.widgets import (
    AutocompleteSelect,
    AutocompleteSelectMultiple,
    ForeignKeyRawIdWidget,
    ManyToManyRawIdWidget,
)
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from server.core.models import Player, User
from server.transaction.models import (
    ManualTransaction,
    PhonePeTransaction,
    RazorpayTransaction,
)

from .test_subscription_admin import ADMIN_STORAGES, staff_user
from .test_subscription_model import make_player

# Tables too big, or too costly per option, to draw as a dropdown.
BIG = {"Player", "User", "Subscription", "RazorpayTransaction", "UCPerson", "Match"}
SEARCHED = (AutocompleteSelect, AutocompleteSelectMultiple)
RAW = (ForeignKeyRawIdWidget, ManyToManyRawIdWidget)


def _editable(model_admin: Any, request: Any) -> bool:
    if isinstance(model_admin, admin.options.InlineModelAdmin):
        can_add = model_admin.has_add_permission(request, None)
    else:
        can_add = model_admin.has_add_permission(request)
    return bool(can_add or model_admin.has_change_permission(request))


def plain_pickers() -> list[str]:
    """Every editable admin form field that draws a big table as a dropdown."""
    request = RequestFactory().get("/admin/")
    request.user = User(is_superuser=True, is_staff=True, is_active=True)
    found = []

    def check(owner: str, form: Any) -> None:
        for name, field in form.base_fields.items():
            queryset = getattr(field, "queryset", None)
            if queryset is None or queryset.model.__name__ not in BIG:
                continue
            widget = getattr(field.widget, "widget", field.widget)
            if not isinstance(widget, SEARCHED + RAW):
                found.append(f"{owner}.{name} ({type(widget).__name__})")

    for model_admin in admin.site._registry.values():
        if _editable(model_admin, request):
            check(type(model_admin).__name__, model_admin.get_form(request))
        for inline in model_admin.get_inline_instances(request):
            if _editable(inline, request):
                owner = f"{type(model_admin).__name__}/{type(inline).__name__}"
                check(owner, inline.get_formset(request).form)
    return found


class TestNoWholeTableDropdowns(TestCase):
    def test_no_form_draws_a_big_table_as_a_dropdown(self) -> None:
        self.assertEqual([], plain_pickers())


@override_settings(STORAGES=ADMIN_STORAGES)
class AdminPageCase(TestCase):
    def setUp(self) -> None:
        self.staff = staff_user("boss@example.com", everything=True)
        self.client.force_login(self.staff)


class TestPagesCostTheSameHoweverManyPlayers(AdminPageCase):
    def count(self) -> int:
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("admin:server_subscription_add"))
        self.assertEqual(200, response.status_code)
        return len(queries)

    def test_subscription_add_page(self) -> None:
        for i in range(3):
            make_player(f"a{i}@example.com")
        self.count()  # the first render warms a cache, one query more
        few = self.count()
        for i in range(40):
            make_player(f"b{i}@example.com")
        self.assertEqual(few, self.count())


class TestEveryListSearches(AdminPageCase):
    def test_every_admin_list_takes_a_search(self) -> None:
        # A mistyped search field only fails when a search runs.
        for model in admin.site._registry:
            url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
            with self.subTest(model=model.__name__):
                self.assertEqual(200, self.client.get(url, {"q": "zz"}).status_code)

    def found(self, url_name: str, term: str) -> str:
        response = self.client.get(reverse(url_name), {"q": term})
        self.assertEqual(200, response.status_code)
        return response.content.decode()

    def order(self, **fields: Any) -> RazorpayTransaction:
        player = make_player("payer@example.com")
        defaults = {"amount": 100, "currency": "INR", "user": player.user}
        return RazorpayTransaction.objects.create(**{**defaults, **fields})

    def test_razorpay_orders_by_order_and_payment_id(self) -> None:
        self.order(order_id="order_FindMe123", payment_id="pay_FindMe456")
        page = "admin:server_razorpaytransaction_changelist"
        self.assertIn("order_FindMe123", self.found(page, "FindMe123"))
        self.assertIn("order_FindMe123", self.found(page, "pay_FindMe456"))
        self.assertNotIn("order_FindMe123", self.found(page, "nothing-like-it"))

    def test_users_by_email(self) -> None:
        user = make_player("someone.unusual@example.com").user
        user.username = "plainname"
        user.save()
        self.assertIn("plainname", self.found("admin:server_user_changelist", "unusual@exa"))

    def test_players_by_iu_id(self) -> None:
        player = make_player("iu@example.com")
        player.user.first_name, player.user.last_name = "Iu", "Holder"
        player.user.save()
        Player.objects.filter(pk=player.pk).update(iu_id="IU-424242")
        self.assertIn("Iu Holder", self.found("admin:server_player_changelist", "424242"))


@override_settings(STORAGES=ADMIN_STORAGES)
class TestRetiredPaymentPages(AdminPageCase):
    def setUp(self) -> None:
        super().setUp()
        user = make_player("old@example.com").user
        self.phonepe = PhonePeTransaction.objects.create(
            transaction_id=uuid.uuid4(), amount=100, currency="INR", user=user
        )
        self.manual = ManualTransaction.objects.create(
            transaction_id="UTR123OLD", amount=100, currency="INR", user=user
        )

    def test_off_the_admin_menu(self) -> None:
        index = self.client.get(reverse("admin:index")).content.decode()
        self.assertNotIn("phonepetransaction", index)
        self.assertNotIn("manualtransaction", index)

    def test_still_viewable_by_direct_link(self) -> None:
        for name, obj in [("phonepetransaction", self.phonepe), ("manualtransaction", self.manual)]:
            with self.subTest(name):
                listing = reverse(f"admin:server_{name}_changelist")
                self.assertEqual(200, self.client.get(listing).status_code)
                change = reverse(f"admin:server_{name}_change", args=[obj.pk])
                self.assertEqual(200, self.client.get(change).status_code)

    def test_cannot_be_added_changed_or_deleted(self) -> None:
        retired: list[tuple[str, PhonePeTransaction | ManualTransaction]] = [
            ("phonepetransaction", self.phonepe),
            ("manualtransaction", self.manual),
        ]
        for name, obj in retired:
            with self.subTest(name):
                add = reverse(f"admin:server_{name}_add")
                self.assertEqual(403, self.client.get(add).status_code)
                change = reverse(f"admin:server_{name}_change", args=[obj.pk])
                self.client.post(change, {"amount": 1})
                obj.refresh_from_db()
                self.assertEqual(100, obj.amount)
                delete = reverse(f"admin:server_{name}_delete", args=[obj.pk])
                self.assertEqual(403, self.client.get(delete).status_code)

    def test_found_by_transaction_id(self) -> None:
        listing = reverse("admin:server_manualtransaction_changelist")
        self.assertIn("UTR123OLD", self.client.get(listing, {"q": "123OLD"}).content.decode())


@override_settings(STORAGES=ADMIN_STORAGES)
class TestAutocomplete(AdminPageCase):
    def test_subscription_player_picker_searches_by_name(self) -> None:
        player = make_player("pick@example.com")
        player.user.first_name, player.user.last_name = "Pickable", "Person"
        player.user.save()
        response = self.client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "server",
                "model_name": "subscription",
                "field_name": "player",
                "term": "Pickable Per",
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual([str(player.pk)], [r["id"] for r in response.json()["results"]])

    def test_pickers_page_in_a_stable_order(self) -> None:
        for model_name, field_name in [
            ("subscription", "player"),
            ("team", "admins"),
            ("formresponse", "transaction"),
        ]:
            with self.subTest(model_name), warnings.catch_warnings():
                warnings.simplefilter("error")
                params = {
                    "app_label": "server",
                    "model_name": model_name,
                    "field_name": field_name,
                    "term": "",
                }
                self.assertEqual(
                    200, self.client.get(reverse("admin:autocomplete"), params).status_code
                )


@override_settings(STORAGES=ADMIN_STORAGES)
class TestMatchStatsAreNotAddedByHand(AdminPageCase):
    def test_no_add_page(self) -> None:
        # Its match would be read-only, and a stats row needs one.
        self.assertEqual(403, self.client.get(reverse("admin:server_matchstats_add")).status_code)

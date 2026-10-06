"""A team's registration page, end to end, against Razorpay's real test mode.

Each payment goes through the real Razorpay test checkout, and each test
asserts what the page shows and what the database holds. Skipped without a
Razorpay test key; never run with a live one.
"""

import datetime
import os
import uuid
from contextlib import ExitStack

import pytest
import razorpay
from django.test import Client
from seleniumbase import BaseCase

from server.core.models import Player, Team, User
from server.registration.models import RosterEntry
from server.series.models import Role, SeriesRegistration, SeriesRosterInvitation
from server.subscription.models import Subscription, SubscriptionPlan
from server.tests import test_subscription_integration as subscription_flows
from server.tests import test_ui
from server.tests.base import make_account
from server.tests.localserver import APP_URL, running_test_server
from server.tests.razorpay_checkout import complete_razorpay_test_payment
from server.tests.test_eligibility import make_series
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Event, Registration, Tournament
from server.transaction.client.razorpay import client_for
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer
from server.utils import today

STATE_KEY_ID = os.environ.get("STATE_RAZORPAY_KEY_ID", "")
STATE_KEY_SECRET = os.environ.get("STATE_RAZORPAY_KEY_SECRET", "")
PLAYER_FEE = 100000  # ₹1,000, open_event's
COMPLETED = RazorpayTransaction.TransactionStatusChoices.COMPLETED
PLAYER_REGISTRATION = RazorpayTransaction.TransactionTypeChoices.PLAYER_REGISTRATION
# Payment confirmed can take up to the page's two minutes of polling.
PAID = 150
ADD_DIALOG = '//dialog[@aria-label="Add players"]'


def row(name: str) -> str:
    """A player's line in either roster section, paid or not."""
    sections = '@aria-labelledby="paid-heading" or @aria-labelledby="unpaid-heading"'
    return f'//section[{sections}]//li[contains(., "{name}")]'


@pytest.mark.django_db(transaction=True)
class RegistrationPageCase(BaseCase):
    """The page against a real server; seeds a series team an admin can roster."""

    sign_in_as = test_ui.TestIntegration.sign_in_as

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Series invites are emailed with a signed link; the server needs a key.
        os.environ.setdefault("EMAIL_SECRET_KEY", "test-invite-key")
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def setUp(self, masterqa_mode: bool = False) -> None:
        super().setUp()
        self.season = subscription_flows.seed_catalog()
        self.series = make_series(self.season)
        self.series.event_max_players_total = 10
        self.series.save()
        self.event = open_event(
            title=f"Club Open {uuid.uuid4().hex[:6]}",
            series=self.series,
            is_subscription_needed=True,
        )
        self.tournament = Tournament.objects.create(event=self.event)
        self.team = Team.objects.create(name="Home Team")
        # In the series and its fee paid: the page opens on the roster step.
        self.series.teams.add(self.team)
        self.tournament.teams.add(self.team)
        self.admin = test_ui.make_player("captain@example.com", first="Asha", last="Captain")
        self.team.admins.add(self.admin)
        self.page = f"/tournament/{self.event.slug}/team/{self.team.slug}/registration"

    # Helpers ####################

    def player(
        self,
        first: str,
        last: str,
        *,
        on_series: bool = True,
        tier: str | None = "regular",
        entry: bool = True,
    ) -> Player:
        user = test_ui.make_player(f"{first.lower()}@example.com", first=first, last=last)
        p = Player.objects.get(user=user)
        if on_series:
            SeriesRegistration.objects.create(
                series=self.series, team=self.team, player=p, role=Role.DEFAULT
            )
        if tier:
            Subscription.objects.create(
                player=p,
                season=self.season,
                plan=SubscriptionPlan.objects.get(season=self.season, type__slug=tier),
                is_active=True,
                waiver_valid=True,
                coc_agreed=True,
                start_date=self.season.start_date,
                end_date=self.season.end_date,
            )
        if entry:
            RosterEntry.objects.create(
                event=self.event, team=self.team, player=p, added_by=self.admin
            )
        return p

    def open_page(self) -> None:
        self.open(f"{APP_URL}{self.page}")
        self.assert_text(self.team.name, "h1")

    def assert_state(self, name: str, text: str, timeout: float = 30) -> None:
        self.assert_text(text, row(name), timeout=timeout)

    def as_user(self, user: User) -> Client:
        client = Client()
        client.force_login(user)
        return client

    def paid_order(self, amount: int) -> RazorpayTransaction:
        order = RazorpayTransaction.objects.get(type=PLAYER_REGISTRATION, status=COMPLETED)
        self.assertEqual(amount, order.amount)
        return order

    def assert_rostered(self, players: list[Player], order: RazorpayTransaction, each: int) -> None:
        self.assertEqual(
            {p.id for p in players},
            set(
                Registration.objects.filter(event=self.event, team=self.team).values_list(
                    "player_id", flat=True
                )
            ),
        )
        self.assertFalse(RosterEntry.objects.filter(event=self.event).exists())
        lines = RazorpayTransactionPlayer.objects.filter(transaction=order)
        self.assertEqual(
            sorted((p.id, each) for p in players),
            sorted(lines.values_list("player_id", "amount")),
        )


@pytest.mark.skipif(
    not os.environ.get("RAZORPAY_KEY_ID", "").startswith("rzp_test_"),
    reason="needs a Razorpay test-mode key",
)
@pytest.mark.django_db(transaction=True)
class TestRegistrationIntegration(RegistrationPageCase):
    # Flows ####################

    def test_a_series_team_builds_and_pays_its_roster(self) -> None:
        on_roster = [self.player(n, "Rao") for n in ("Kiran", "Meera", "Tara")]
        newcomer = self.player("Vikram", "Singh", on_series=False, entry=False)

        self.sign_in_as(self.admin)
        self.open_page()
        for p in on_roster:
            self.assert_state(p.user.get_full_name(), "Ready to pay")
        self.assert_element('button:contains("Pay ₹3,000")')

        # Not on the series roster: adding them invites them to it.
        self.click('button:contains("+ Add players")')
        self.type("#add-players-search", "Vikram")
        self.click(f'{ADD_DIALOG}//button[@aria-label="Invite Vikram Singh"]')
        self.assert_text("✓ Added", ADD_DIALOG)
        self.click(f'{ADD_DIALOG}//button[text()="Done"]')
        self.assert_state("Vikram Singh", "Invite sent")
        self.assert_element('button:contains("Pay ₹3,000")')
        invite = SeriesRosterInvitation.objects.get(to_player=newcomer, team=self.team)
        self.assertEqual(SeriesRosterInvitation.Status.PENDING, invite.status)

        # They accept it, as the invite's own page does.
        response = self.as_user(newcomer.user).put(f"/api/series/invitation/{invite.id}/accept")
        self.assertEqual(200, response.status_code, response.content)
        self.open_page()
        for p in [*on_roster, newcomer]:
            self.assert_state(p.user.get_full_name(), "Ready to pay")
        self.assert_text("4 players ready", "[data-pay-bar]")
        self.assert_element('[data-pay-bar] button:contains("Pay ₹4,000")')

        complete_razorpay_test_payment(self, 'button:contains("Pay ₹4,000")')
        self.assert_text("Paid. 4 players rostered.", timeout=PAID)
        order = self.paid_order(4 * PLAYER_FEE)
        self.assert_rostered([*on_roster, newcomer], order, PLAYER_FEE)
        # Paid rows carry no status line now; being in the Paid list says it.
        for p in [*on_roster, newcomer]:
            name = p.user.get_full_name()
            self.assert_element(f'//ul[@aria-label="Paid"]/li[contains(., "{name}")]')

    def test_subscription_handoff_round_trip(self) -> None:
        players = [self.player(n, "Iyer", tier=None) for n in ("Kiran", "Meera")]
        names = [p.user.get_full_name() for p in players]

        self.sign_in_as(self.admin)
        self.open_page()
        for name in names:
            self.assert_state(name, "No subscription")
        self.click('a:contains("Pay ₹1,500")')

        # Both picked, for this team, and paid for together.
        self.assert_text(f"For Home Team · {self.event.title}")
        for name in names:
            self.assert_element(subscription_flows.selected_row(name))
        self.assert_text("Pay ₹1,500", 'button:contains("Pay ₹")')
        complete_razorpay_test_payment(self, 'button:contains("Pay ₹1,500")')
        self.assert_text("Payment successfully completed", timeout=60)
        for p in players:
            self.assertTrue(Subscription.objects.get(player=p, season=self.season).is_active)

        self.click('a:contains("Back to your team\'s registration")')
        self.assert_text(self.team.name, "h1")
        self.assertTrue(self.get_current_url().endswith(self.page))
        # Bought for them, so the waiver is still theirs to sign.
        for name in names:
            self.assert_state(name, "Waiver not signed")
        for p in players:
            response = self.as_user(p.user).post(
                "/api/waiver", {"player_id": p.id}, content_type="application/json"
            )
            self.assertEqual(200, response.status_code, response.content)
            response = self.as_user(p.user).post(
                "/api/code-of-conduct", {"player_id": p.id}, content_type="application/json"
            )
            self.assertEqual(200, response.status_code, response.content)
        self.open_page()
        for name in names:
            self.assert_state(name, "Ready to pay")
        self.assert_text("2 players ready", "[data-pay-bar]")
        self.assert_element('[data-pay-bar] button:contains("Pay ₹2,000")')

    def test_late_fee_change_asks_first(self) -> None:
        p = self.player("Kiran", "Rao")
        self.sign_in_as(self.admin)
        self.open_page()
        self.assert_text("1 player ready", "[data-pay-bar]")
        self.assert_element('[data-pay-bar] button:contains("Pay ₹1,000")')

        # A late fee starts while the page is open.
        day = today()
        Event.objects.filter(pk=self.event.pk).update(
            player_registration_end_date=day - datetime.timedelta(days=1),
            player_late_penalty=20000,
            player_late_penalty_end_date=day + datetime.timedelta(days=5),
        )
        self.click('button:contains("Pay ₹1,000")')
        self.assert_text("The total changed", "dialog[open]")
        self.assert_text("₹1,000 → ₹1,200", "dialog[open]")
        self.assert_element('dialog[open] button:contains("Cancel")')
        self.assertFalse(RazorpayTransaction.objects.exists())

        complete_razorpay_test_payment(self, 'dialog[open] button:contains("Pay ₹1,200")')
        self.assert_text("Paid. 1 player rostered.", timeout=PAID)
        order = self.paid_order(120000)
        self.assert_rostered([p], order, 120000)

    @pytest.mark.skipif(
        not STATE_KEY_ID.startswith("rzp_test_"), reason="needs the state's Razorpay test key"
    )
    def test_routed_to_the_state_account(self) -> None:
        account = make_account(
            "test-state",
            name="Test State Association",
            key_id=STATE_KEY_ID,
            key_secret=STATE_KEY_SECRET,
            webhook_secret=uuid.uuid4().hex,
        )
        Event.objects.filter(pk=self.event.pk).update(payment_account=account)
        p = self.player("Kiran", "Rao")

        self.sign_in_as(self.admin)
        self.open_page()
        self.assert_text("Paid to Test State Association")
        complete_razorpay_test_payment(self, 'button:contains("Pay ₹1,000")')
        self.assert_text("Paid. 1 player rostered.", timeout=PAID)

        order = self.paid_order(PLAYER_FEE)
        self.assert_rostered([p], order, PLAYER_FEE)
        self.assertEqual(account, order.account)
        payment = client_for(account).payment.fetch(order.payment_id)
        self.assertEqual("captured", payment["status"])
        self.assertEqual(PLAYER_FEE, payment["amount"])
        self.assertEqual(order.order_id, payment["order_id"])
        # Our keys can't see it: it is not in our account at all.
        with self.assertRaises(razorpay.errors.BadRequestError):
            client_for(None).order.fetch(order.order_id)

    def test_every_greyed_button_says_why(self) -> None:
        # One spot, taken by a paid player, so a fully eligible one is over it.
        self.series.event_max_players_total = 1
        self.series.save()
        paid = self.player("Arjun", "Paid", entry=False)
        Registration.objects.create(event=self.event, team=self.team, player=paid)
        self.player("Lata", "Full")
        invited = self.player("Kiran", "Waits", on_series=False)
        SeriesRosterInvitation.objects.create(
            series=self.series, from_user=self.admin, to_player=invited, team=self.team
        )
        rivals = Team.objects.create(name="Rivals")
        self.series.teams.add(rivals)
        taken = self.player("Meera", "Elsewhere", on_series=False)
        SeriesRegistration.objects.create(series=self.series, team=rivals, player=taken)

        self.sign_in_as(self.admin)
        self.open_page()
        self.assert_element('//ul[@aria-label="Paid"]/li[contains(., "Arjun Paid")]')
        self.assert_state("Lata Full", "Roster full")
        self.assert_state("Kiran Waits", "Invite sent")
        self.assert_state("Meera Elsewhere", "On Rivals's series roster")
        # Someone already on the list has no Add button in the search.
        self.click('button:contains("+ Add players")')
        self.type("#add-players-search", "Lata")
        self.assert_text("On the list", f'{ADD_DIALOG}//li[contains(., "Lata Full")]')
        # Its first fetch stays inside the dialog: the page doesn't suspend
        # and drop it out of the top layer.
        self.assertTrue(
            self.execute_script(
                """return document.querySelector('dialog[aria-label="Add players"]')
                .matches(":modal")"""
            )
        )
        self.assert_text(self.team.name, "h1")
        self.assert_element_absent('button[aria-label="Add Lata Full"]')
        self.click(f'{ADD_DIALOG}//button[text()="Done"]')

        greyed = self.execute_script(
            """
            return Array.from(document.querySelectorAll('[aria-disabled="true"]')).map(el => {
              const id = el.getAttribute("aria-describedby");
              const reason = id && document.getElementById(id);
              return [el.textContent.trim(), reason ? reason.textContent.trim() : ""];
            });
            """
        )
        reasons = dict(greyed)
        self.assertEqual(len(greyed), len(reasons), greyed)
        for label, reason in greyed:
            self.assertTrue(reason, f"{label!r} is greyed with no reason")
        self.assertEqual("Waiting on 1 player", reasons.get("Pay ₹0"), greyed)

        # Paid rows can't be removed; the others ask first, and say when
        # removing also withdraws a series invite.
        self.assert_element_absent('button[aria-label="Remove Arjun Paid"]')
        self.click('button[aria-label="Remove Kiran Waits"]')
        self.assert_text("This also withdraws their series invite.", "dialog[open]")
        self.click('//dialog[@open]//button[normalize-space()="Remove"]')
        self.assert_text("Removed Kiran Waits", '[role="status"]')
        self.assert_element_absent(row("Kiran Waits"))
        self.assertEqual(
            SeriesRosterInvitation.Status.REVOKED,
            SeriesRosterInvitation.objects.get(to_player=invited).status,
        )

    def test_a_foreign_return_link_is_ignored(self) -> None:
        stranger, member = (self.player(n, "Iyer", tier=None) for n in ("Kiran", "Meera"))
        self.sign_in_as(self.admin)

        # Anywhere but a team's registration page: no banner, and no way "back".
        self.open(
            f"{APP_URL}/subscription/group?players={stranger.id}"
            f"&tiers={stranger.id}:regular&return=https://example.com"
        )
        self.assert_element(subscription_flows.selected_row("Kiran Iyer"))
        self.assert_text_not_visible("to be rostered")
        complete_razorpay_test_payment(self, 'button:contains("Pay ₹750")')
        self.assert_text("Payment successfully completed", timeout=60)
        self.assert_element_absent('a:contains("Back to your team\'s registration")')
        self.assert_text_not_visible("to be rostered")

        # The same link back to this team's page: both are there.
        self.open(
            f"{APP_URL}/subscription/group?players={member.id}"
            f"&tiers={member.id}:regular&return={self.page}"
        )
        self.assert_element(subscription_flows.selected_row("Meera Iyer"))
        self.assert_text(f"For Home Team · {self.event.title}")
        complete_razorpay_test_payment(self, 'button:contains("Pay ₹750")')
        self.assert_text("Payment successfully completed", timeout=60)
        self.click('a:contains("Back to your team\'s registration")')
        self.assert_text(self.team.name, "h1")
        self.assertTrue(self.get_current_url().endswith(self.page))

    def test_add_players_from_the_dialog_including_myself(self) -> None:
        past = self.player("Pia", "Past", on_series=False, entry=False)
        old = Event.objects.create(
            title="Old Cup",
            start_date=today() - datetime.timedelta(days=40),
            end_date=today() - datetime.timedelta(days=38),
            team_registration_start_date=today() - datetime.timedelta(days=80),
            team_registration_end_date=today() - datetime.timedelta(days=60),
            player_registration_start_date=today() - datetime.timedelta(days=80),
            player_registration_end_date=today() - datetime.timedelta(days=60),
        )
        Registration.objects.create(event=old, team=self.team, player=past)
        me = Player.objects.get(user=self.admin)
        SeriesRegistration.objects.create(
            series=self.series, team=self.team, player=me, role=Role.DEFAULT
        )

        self.sign_in_as(self.admin)
        self.open_page()
        self.click('button:contains("+ Add players")')
        # The heading is uppercased on screen; its list carries the title.
        past_group = f'{ADD_DIALOG}//ul[@aria-label="Played for Home Team before"]'
        self.assert_text("Last: Old Cup", f'{past_group}/li[contains(., "Pia Past")]')
        self.click(f'{ADD_DIALOG}//button[@aria-label="Add {me.user.get_full_name()}"]')
        self.assert_text("✓ Added", ADD_DIALOG)
        self.click(f'{ADD_DIALOG}//button[@aria-label="Invite Pia Past"]')
        self.click(f'{ADD_DIALOG}//button[normalize-space()="Done"]')
        self.assert_element('//ul[@aria-label="Not paid"]/li[contains(., "Pia Past")]')
        self.assert_element('//ul[@aria-label="Not paid"]/li[contains(., "Asha Captain")]')
        self.assertTrue(RosterEntry.objects.filter(event=self.event, player=me).exists())
        self.assertFalse(SeriesRosterInvitation.objects.filter(to_player=me).exists())
        self.assertTrue(SeriesRosterInvitation.objects.filter(to_player=past).exists())

    def test_pay_then_swap(self) -> None:
        ravi = self.player("Ravi", "Ready")
        self.sign_in_as(self.admin)
        self.open_page()
        complete_razorpay_test_payment(self, 'button:contains("Pay ₹1,000")')
        self.assert_text("Paid. 1 player rostered.", timeout=PAID)
        order = self.paid_order(PLAYER_FEE)
        self.assert_rostered([ravi], order, PLAYER_FEE)
        self.assert_element('//ul[@aria-label="Paid"]/li[contains(., "Ravi Ready")]')
        self.assert_element_absent('//ul[@aria-label="Paid"]//button')

        kiran = self.player("Kiran", "Extra")
        self.open_page()
        self.click('button:contains("Swap a player")')
        dialog = '//dialog[@aria-label="Swap a player"]'
        self.click(f'{dialog}//label[contains(., "Ravi Ready")]')
        self.click(f'{dialog}//label[contains(., "Kiran Extra")]')
        self.click(f'{dialog}//button[contains(., "Swap Ravi → Kiran")]')
        self.assert_element('//ul[@aria-label="Paid"]/li[contains(., "Swapped in for Ravi Ready")]')
        self.assert_element('//ul[@aria-label="Not paid"]/li[contains(., "Ravi Ready")]')
        self.assertTrue(Registration.objects.filter(event=self.event, player=kiran).exists())
        self.assertFalse(Registration.objects.filter(event=self.event, player=ravi).exists())

    def test_home_card_and_tournament_page_lead_to_registration(self) -> None:
        self.tournament.status = Tournament.Status.SCHEDULING
        self.tournament.save()
        self.sign_in_as(self.admin)

        # One admin team: the registration list goes straight to its page.
        self.open(APP_URL)
        self.click(f'a[href="/tournament/{self.event.slug}/register"]')
        self.assert_text(self.team.name, "h1")
        self.assert_url_contains(self.page)

        self.open(f"{APP_URL}/tournament/{self.event.slug}")
        self.click('a:contains("Register your team")')
        self.assert_text(self.team.name, "h1")
        self.assert_url_contains(self.page)

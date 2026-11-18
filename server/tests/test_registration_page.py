"""The team registration page on a phone: what fits, and what it says.

No payments happen here, so these run without a Razorpay key.
"""

import datetime
import os

import pytest

from server.core.models import Player
from server.registration.models import RosterEntry
from server.series.models import Role, SeriesRegistration
from server.tests.localserver import APP_URL
from server.tests.test_registration_integration import ADD_DIALOG, RegistrationPageCase, row
from server.tournament.models import Event, Registration, Tournament
from server.utils import today

PHONE = (390, 844)
PIXEL = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="


# "Integration" in the name puts it in CI's browser job, which builds the
# frontend; the unit job runs `-k 'not Integration'` with no frontend.
@pytest.mark.django_db(transaction=True)
class TestRegistrationPageIntegration(RegistrationPageCase):
    def paid(self, first: str, last: str, **fields: bool | str | None) -> Player:
        p = self.player(first, last, entry=False, **fields)  # type: ignore[arg-type]
        Registration.objects.create(event=self.event, team=self.team, player=p)
        return p

    def open_phone(self) -> None:
        self.sign_in_as(self.admin)
        self.set_window_size(*PHONE)
        self.open_page()

    def rect(self, selector: str, side: str) -> float:
        script = f"return document.querySelector({selector!r}).getBoundingClientRect().{side}"
        return float(self.execute_script(script))

    def test_the_page_opens_on_a_phone(self) -> None:
        self.player("Ravi", "Ready")
        self.open_phone()
        self.assert_state("Ravi Ready", "Ready to pay")

    def test_paid_players_come_after_the_rest(self) -> None:
        self.paid("Meera", "Paid")
        self.player("Ravi", "Ready")
        self.open_phone()
        self.assertLess(self.rect("#unpaid-heading", "top"), self.rect("#paid-heading", "top"))
        # A paid row says nothing more unless the player was swapped in.
        self.assert_element('//ul[@aria-label="Paid"]/li[contains(., "Meera Paid")]')
        self.assert_element_absent('//ul[@aria-label="Paid"]/li[contains(., "Rostered")]')

    def test_city_shows_only_for_shared_names(self) -> None:
        self.player("Ravi", "Kumar")
        twin = self.player("Ravi2", "Kumar")
        twin.user.first_name = "Ravi"
        twin.user.save()
        twin.city = "Chennai"
        twin.save()
        self.player("Dev", "Solo")
        self.open_phone()
        self.assert_text("Chennai", '//section[@aria-labelledby="unpaid-heading"]')
        self.assertNotIn("Bengaluru", self.get_text(row("Dev Solo")))

    def test_a_photo_or_initials(self) -> None:
        pic = self.player("Ravi", "Ready")
        pic.profile_pic_url = PIXEL
        pic.save()
        gone = self.player("Dev", "Broken")
        gone.profile_pic_url = "http://localhost:1/missing.png"
        gone.save()
        self.open_phone()
        self.assert_element(f"{row('Ravi Ready')}//img")
        self.assert_element_absent(f"{row('Dev Broken')}//img")
        self.assert_text("DB", row("Dev Broken"))

    def test_remove_is_quiet_until_pointed_at(self) -> None:
        self.player("Ravi", "Ready")
        self.open_phone()
        button = f'{row("Ravi Ready")}//button[@aria-label="Remove Ravi Ready"]'
        self.assert_element(f"{button}//*[local-name()='svg']")
        self.assert_element_absent(f"{button}//*[contains(@class, 'bg-red-100')]")

    def test_totals_on_one_line(self) -> None:
        self.series.event_min_players_male = 2
        self.series.save()
        self.player("Ravi", "Ready")  # male-matching
        self.open_phone()
        meta = 'section[aria-labelledby="step-roster"] [data-roster-totals]'
        self.assert_text("1/10", meta)
        self.assert_text("1 M, need 2", meta)

    def test_totals_skip_a_gender_the_series_allows_none_of(self) -> None:
        self.series.event_max_players_female = 0
        self.series.save()
        self.player("Ravi", "Ready")
        self.open_phone()
        meta = 'section[aria-labelledby="step-roster"] [data-roster-totals]'
        self.assertNotIn("F", self.get_text(meta))

    def test_players_show_on_the_first_screen(self) -> None:
        self.paid("Meera", "Paid")
        self.paid("Kavya", "Paid")
        self.player("Ravi", "Ready")
        self.player("Arjun", "Kumar", tier=None)
        self.open_phone()
        first = 'section[aria-labelledby="unpaid-heading"] li'
        self.assertLess(self.rect(first, "bottom"), self.rect("[data-pay-bar]", "top"))

    def test_done_steps_share_one_line(self) -> None:
        self.player("Ravi", "Ready")
        self.open_phone()
        self.assert_text("In Club series")
        self.assert_text("Team fee paid")
        self.assert_element_absent('section[aria-labelledby="step-series"]')
        self.assert_element_absent('section[aria-labelledby="step-team_fee"]')
        self.assert_element('section[aria-labelledby="step-roster"]')
        self.assert_element_absent('[role="progressbar"]')
        self.assert_element_absent('ul[aria-label="Deadlines"]')

    def test_all_set(self) -> None:
        self.paid("Meera", "Paid")
        self.paid("Kavya", "Paid")
        self.open_phone()
        self.assert_text("You're all set. 2 players paid.")
        self.assert_text("Roster paid")
        # Nobody left to pay for, so no pay bar saying "Pay ₹0".
        self.assert_element_absent("[data-pay-bar]")

    def test_fee_due(self) -> None:
        self.tournament.teams.remove(self.team)
        self.open_phone()
        self.assert_text("₹5,000, or ₹2,000 now and the rest later")
        self.assert_element('button:contains("Pay ₹2,000")')
        # Captains add players before paying the fee.
        self.assert_element(
            'section[aria-labelledby="step-roster"] button:contains("+ Add people")'
        )

    def test_pay_bar_says_it_once(self) -> None:
        self.player("Ravi", "Ready")
        self.open_phone()
        bar = "[data-pay-bar]"
        self.assert_text("1 player ready", bar)
        self.assertNotIn("each", self.get_text(bar))
        self.assertNotIn("Paid to", self.get_text(bar))
        self.assert_element(f'{bar} button:contains("Pay ₹1,000")')

    def test_help_button_clears_the_pay_bar(self) -> None:
        # Nobody ready: the bar is at its tallest, with its reason line.
        self.player("Arjun", "Kumar", tier=None)
        self.open_phone()
        self.assert_text("No players ready yet", "[data-pay-bar]")
        self.assert_help_clears_the_bar()
        # However tall wrapping text (a narrower phone, bigger fonts) makes it.
        self.execute_script("document.querySelector('[data-pay-bar]').style.paddingTop = '80px'")
        self.assert_help_clears_the_bar()

    def assert_help_clears_the_bar(self) -> None:
        # The button glides up (a 300ms transition), so a slow machine can
        # measure it on the way.
        def gap() -> float:
            help_bottom = self.rect('a[title="Access Help Center"]', "bottom")
            return self.rect("[data-pay-bar]", "top") - help_bottom

        for _ in range(20):
            if gap() >= 0:
                return
            self.sleep(0.1)
        self.assertGreaterEqual(gap(), 0)

    def test_add_dialog_shows_photos(self) -> None:
        pia = self.player("Pia", "Pic", entry=False)  # on the series roster
        pia.profile_pic_url = PIXEL
        pia.save()
        self.open_phone()
        self.click('button:contains("+ Add people")')
        self.assert_element(f'{ADD_DIALOG}//li[contains(., "Pia Pic")]//img')

    def test_admin_adds_a_coach(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(series=None, non_player_fee=30000)
        coach = self.player("Kiran", "Coach", on_series=False, tier="community", entry=False)
        self.open_phone()
        self.click('button:contains("+ Add people")')
        self.type("#add-players-search", "Kiran")
        kiran = f'{ADD_DIALOG}//li[contains(., "Kiran Coach")]'
        self.assert_text("You'll set each person's role on the roster", ADD_DIALOG)
        # Community covers coaching but not playing, and the row says both.
        self.assert_text("As player: Subscription needs an upgrade", kiran)
        self.assert_text("As coach or manager: Ready to pay", kiran)
        self.click(f'{kiran}//button[@aria-label="Add Kiran Coach"]')
        self.assert_text("✓ Added", kiran)
        undo = f'{kiran}//button[@aria-label="Undo adding Kiran Coach"]'
        self.assertTrue(
            self.execute_script(
                "return document.activeElement === arguments[0]", self.find_element(undo)
            )
        )
        self.click(f'{ADD_DIALOG}//button[normalize-space()="Done"]')

        # Roles are set on the roster, before paying; the price follows.
        self.assert_text("Everyone is a player unless you change their role", "body")
        self.assert_text("and pay ₹300 each", "body")
        role = f'{row("Kiran Coach")}//select[@aria-label="Role for Kiran Coach"]'
        self.assertEqual("DFLT", self.find_element(role).get_attribute("value"))
        self.select_option_by_value(role, "COACH")
        self.assert_text("Kiran Coach is now a coach", "body")
        # Keyboard users stay on the role they changed.
        self.assertEqual(
            "Role for Kiran Coach",
            self.execute_script("return document.activeElement.getAttribute('aria-label')"),
        )
        self.assert_state("Kiran Coach", "Ready to pay")
        self.assert_text("1 non-player ready", "[data-pay-bar]")
        self.assert_text("0 players · 1 non-player", "[data-roster-totals]")
        self.assert_text("Pay ₹300", "[data-pay-bar]")
        self.assertEqual(Role.COACH, RosterEntry.objects.get(player=coach).role)

    def test_a_series_member_keeps_their_series_role(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(non_player_fee=30000)
        coach = self.player("Kiran", "Coach", entry=False)  # on the series roster
        SeriesRegistration.objects.filter(player=coach).update(role=Role.COACH)
        self.open_phone()
        self.click('button:contains("+ Add people")')
        self.assert_text("Roles come from the series roster.", ADD_DIALOG)
        link = f'{ADD_DIALOG}//a[normalize-space()="Edit series roster"]'
        self.assertTrue(
            self.get_attribute(link, "href").endswith(
                f"/series/{self.series.slug}/team/{self.team.slug}"
            )
        )
        kiran = f'{ADD_DIALOG}//li[contains(., "Kiran Coach")]'
        self.assert_text("Series role: Coach", kiran)
        self.assert_text("No player spot · ₹300", kiran)
        # Their role is the series one, so there's no other role to pick.
        self.assert_element_absent(f'{ADD_DIALOG}//li[contains(., "Kiran Coach")]//select')
        self.click(f'{ADD_DIALOG}//button[@aria-label="Add Kiran Coach as coach"]')
        self.assert_text("Added as Coach", ADD_DIALOG)
        self.click(f'{ADD_DIALOG}//button[normalize-space()="Done"]')
        self.assert_text("1 non-player", "[data-roster-totals]")
        # On the roster too, the series role stands.
        self.assert_element_absent(f'{row("Kiran Coach")}//select')

    def test_the_registration_list_reads_each_window(self) -> None:
        t = today()
        Event.objects.filter(pk=self.event.pk).update(
            non_player_fee=30000,
            team_registration_start_date=t + datetime.timedelta(days=3),
            team_registration_end_date=t + datetime.timedelta(days=6),
            team_late_penalty_end_date=t + datetime.timedelta(days=6),
            player_registration_start_date=t - datetime.timedelta(days=10),
            player_registration_end_date=t - datetime.timedelta(days=5),
            player_late_penalty_end_date=t - datetime.timedelta(days=2),
        )
        self.tournament.status = Tournament.Status.SCHEDULING
        self.tournament.save()
        self.open_phone()
        self.open(f"{APP_URL}/tournament/{self.event.slug}/register?all")
        opens = t + datetime.timedelta(days=3)
        ended = t - datetime.timedelta(days=2)  # the late window's last day
        self.wait_for_text("Player Registration", "body")
        shown = " ".join(self.get_text("body").lower().split())
        self.assertIn(f"opens {opens:%b} {opens.day}".lower(), shown)
        self.assertIn(f"ended {ended:%b} {ended.day}".lower(), shown)
        self.assertIn("₹300 per non-player", shown)

    def test_before_its_live_the_crumb_leads_back_to_registration(self) -> None:
        self.tournament.status = Tournament.Status.SCHEDULING
        self.tournament.save()
        self.open_phone()
        self.click(f'nav a[href="/tournament/{self.event.slug}/register?all"]')
        # A one-team admin isn't sent straight back to their team's page.
        self.assert_element(f'a[href="{self.page}"]')
        self.assert_url_contains(f"/tournament/{self.event.slug}/register?all")

    def test_a_live_tournaments_crumb_leads_to_its_page(self) -> None:
        self.tournament.status = Tournament.Status.LIVE
        self.tournament.save()
        self.open_phone()
        self.assert_element(f'nav a[href="/tournament/{self.event.slug}"]')

    def test_swap_dialog_wording(self) -> None:
        self.paid("Meera", "Paid")
        self.player("Ravi", "Ready")
        self.open_phone()
        self.click('button:contains("Swap a player")')
        dialog = '//dialog[@aria-label="Swap a player"]'
        self.assert_text("Give a paid spot to someone else. Free, until", dialog)
        # The legends are upper-cased by CSS, so match their source text.
        self.assert_element(f'{dialog}//legend[normalize-space()="Taking off"]')
        self.assert_element(f'{dialog}//legend[normalize-space()="Putting on"]')
        self.assert_element(
            f'{dialog}//label[contains(., "Ravi Ready")]//span[@aria-hidden="true"]'
        )


ALIASES = {"Asia/Kolkata": "Asia/Calcutta"}


class DeadlineDaysIntegrationCase(RegistrationPageCase):
    """The tournament page and the registration list, seen from one time zone."""

    __test__ = False  # only the zones below run
    zone = "UTC"

    def setUp(self, masterqa_mode: bool = False) -> None:
        # Firefox (CI) takes its zone from TZ when it starts; Chrome from CDP.
        before = os.environ.get("TZ")
        os.environ["TZ"] = self.zone
        try:
            super().setUp()
        finally:
            if before is None:
                del os.environ["TZ"]
            else:
                os.environ["TZ"] = before
        if self.browser == "chrome":
            self.driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": self.zone})

    def test_deadlines_read_their_own_day(self) -> None:
        end = self.event.player_registration_end_date
        self.tournament.status = Tournament.Status.SCHEDULING
        self.tournament.save()
        self.sign_in_as(self.admin)
        self.set_window_size(*PHONE)
        zone = self.execute_script("return Intl.DateTimeFormat().resolvedOptions().timeZone")
        self.assertIn(zone, {self.zone, ALIASES.get(self.zone)})
        for page in (
            f"/tournament/{self.event.slug}",
            f"/tournament/{self.event.slug}/register?all",
        ):
            self.open(f"{APP_URL}{page}")
            self.wait_for_text("Open", "body")
            # Capitalized by CSS and split over lines, as the text reads.
            shown = " ".join(self.get_text("body").lower().split())
            self.assertIn(f"open till {end:%b} {end.day}".lower(), shown)
            self.assertNotIn("invalid date", shown)


class TestDeadlinesInIndiaIntegration(DeadlineDaysIntegrationCase):
    __test__ = True
    zone = "Asia/Kolkata"


class TestDeadlinesInTheUSIntegration(DeadlineDaysIntegrationCase):
    __test__ = True
    zone = "America/Los_Angeles"

"""The team registration page on a phone: what fits, and what it says.

No payments happen here, so these run without a Razorpay key.
"""

import pytest

from server.core.models import Player
from server.tests.test_registration_integration import ADD_DIALOG, RegistrationPageCase, row
from server.tournament.models import Registration

PHONE = (390, 844)
PIXEL = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="


@pytest.mark.django_db(transaction=True)
class TestRegistrationPage(RegistrationPageCase):
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

    def test_fee_due(self) -> None:
        self.tournament.teams.remove(self.team)
        self.open_phone()
        self.assert_text("₹5,000, or ₹2,000 now and the rest later")
        self.assert_element('button:contains("Pay ₹2,000")')
        # Captains add players before paying the fee.
        self.assert_element(
            'section[aria-labelledby="step-roster"] button:contains("+ Add players")'
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
        help_button = 'a[title="Access Help Center"]'
        self.assertLessEqual(self.rect(help_button, "bottom"), self.rect("[data-pay-bar]", "top"))

    def test_add_dialog_shows_photos(self) -> None:
        pia = self.player("Pia", "Pic", entry=False)  # on the series roster
        pia.profile_pic_url = PIXEL
        pia.save()
        self.open_phone()
        self.click('button:contains("+ Add players")')
        self.assert_element(f'{ADD_DIALOG}//li[contains(., "Pia Pic")]//img')

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

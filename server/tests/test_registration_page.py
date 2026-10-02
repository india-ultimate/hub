"""The team registration page on a phone: what fits, and what it says.

No payments happen here, so these run without a Razorpay key.
"""

import pytest

from server.core.models import Player
from server.tests.test_registration_integration import RegistrationPageCase, row
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

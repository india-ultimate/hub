"""The team registration page on a phone: what fits, and what it says.

No payments happen here, so these run without a Razorpay key.
"""

import pytest

from server.core.models import Player
from server.tests.test_registration_integration import RegistrationPageCase
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

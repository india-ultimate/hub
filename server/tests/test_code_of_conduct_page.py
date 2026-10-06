"""The code of conduct page on a phone. "Integration" in the class name puts
it in CI's browser job."""

import datetime

import pytest
from django.utils.timezone import now

from server.core.models import Guardianship, Player
from server.subscription.models import Subscription
from server.tests.localserver import APP_URL
from server.tests.test_registration_integration import RegistrationPageCase
from server.utils import today


@pytest.mark.django_db(transaction=True)
class TestCodeOfConductPageIntegration(RegistrationPageCase):
    def member(self, first: str, *, minor: bool = False) -> Player:
        p = self.player(first, "Kumar", entry=False)
        Subscription.objects.filter(player=p).update(coc_agreed=False)
        if minor:
            p.date_of_birth = today() - datetime.timedelta(days=15 * 365)
            p.save()
        return p

    def open_page(self, player: Player) -> None:  # type: ignore[override]
        self.set_window_size(390, 844)
        self.open(f"{APP_URL}/code-of-conduct/{player.id}")
        self.assert_text("Code of conduct", "h1")

    def test_an_adult_agrees(self) -> None:
        p = self.member("Ravi")
        self.sign_in_as(p.user)
        self.open_page(p)
        self.assert_text("Prohibited Conduct")
        button = 'button:contains("I agree")'
        self.assert_attribute(button, "aria-disabled", "true")
        self.assert_text("Tick the box first")
        self.click('label:contains("I have read, understood and agree")')
        self.click(button)
        self.assert_element("#coc-agreed")
        self.assert_text("Agreed by Ravi Kumar", "#coc-agreed")
        # Focus lands on the confirmation, not lost with the button.
        self.assertEqual("coc-agreed", self.execute_script("return document.activeElement.id"))
        self.assertTrue(Subscription.objects.get(player=p).coc_agreed)

    def test_guardian_sees_their_wards_wording(self) -> None:
        kid = self.member("Tara", minor=True)
        Guardianship.objects.create(user=self.admin, player=kid, relation="MO")
        self.sign_in_as(self.admin)
        self.open_page(kid)
        self.assert_text("I have read this Code of Conduct with Tara Kumar")
        self.click('label:contains("I have read this Code of Conduct with")')
        self.click('button:contains("I agree")')
        self.assert_element("#coc-agreed")
        sub = Subscription.objects.get(player=kid)
        self.assertEqual(self.admin, sub.coc_agreed_by)

    def test_a_minor_is_sent_to_their_guardian(self) -> None:
        kid = self.member("Tara", minor=True)
        Guardianship.objects.create(user=self.admin, player=kid, relation="MO")
        self.sign_in_as(kid.user)
        self.open_page(kid)
        self.assert_text("Your guardian needs to agree to this for you")
        self.assert_element_absent('button:contains("I agree")')

    def test_the_profile_step_turns_green(self) -> None:
        p = self.member("Ravi")
        self.sign_in_as(p.user)
        self.set_window_size(390, 844)
        self.open(f"{APP_URL}/dashboard")
        step = f'//li[a[@href="/code-of-conduct/{p.id}"]]'
        self.assert_element(f'{step}[contains(@class, "text-red-600")]')
        self.open_page(p)
        self.click('label:contains("I have read, understood and agree")')
        self.click('button:contains("I agree")')
        self.assert_element("#coc-agreed")
        self.open(f"{APP_URL}/dashboard")
        self.assert_element(f'{step}[contains(@class, "text-green-600")]')

    def test_the_waiver_points_to_the_code_of_conduct(self) -> None:
        p = self.member("Ravi")  # the helper signs the waiver
        self.sign_in_as(p.user)
        self.open(f"{APP_URL}/waiver/{p.id}")
        self.assert_element(
            f'//a[@href="/code-of-conduct/{p.id}"][contains(., "Next: agree to the code of conduct")]'
        )

    def test_an_offline_agreement_shows_the_date_without_a_name(self) -> None:
        p = self.member("Ravi")
        Subscription.objects.filter(player=p).update(coc_agreed=True, coc_agreed_at=now())
        self.sign_in_as(p.user)
        self.open_page(p)
        self.assert_text("Agreed on", "#coc-agreed")
        self.assertNotIn("Agreed by", self.get_text("#coc-agreed"))

"""The guardian card and Change guardian on a phone. "Integration" in the
class name puts it in CI's browser job."""

import datetime

import pytest
from django.utils import timezone

from server.core.models import Guardianship, Player
from server.guardians import emails, tokens
from server.subscription.models import Subscription
from server.task.models import Task
from server.tests import test_ui
from server.tests.localserver import APP_URL, DJANGO_URL
from server.tests.test_registration_integration import RegistrationPageCase, row
from server.utils import today


@pytest.mark.django_db(transaction=True)
class TestGuardiansIntegration(RegistrationPageCase):
    def minor_with_guardian(self) -> Player:
        kid = self.player("Tara", "Kumar", entry=False)
        Subscription.objects.filter(player=kid).update(waiver_valid=False, coc_agreed=False)
        kid.date_of_birth = today() - datetime.timedelta(days=15 * 365)
        kid.save()
        parent = test_ui.make_player("senthil@example.com", first="Senthil", last="J")
        Guardianship.objects.create(user=parent, player=kid, relation="LG")
        return kid

    def test_a_minor_changes_their_guardian(self) -> None:
        kid = self.minor_with_guardian()
        self.sign_in_as(kid.user)
        self.set_window_size(390, 844)
        self.open(f"{APP_URL}/waiver/{kid.id}")
        self.assert_text("senthil@example.com", f"#guardian-card-{kid.id}")
        self.assert_text("Waiting for the guardian to sign", f"#guardian-card-{kid.id}")
        self.click(f"#guardian-change-{kid.id} button")
        self.type('input[name="first_name"]', "Maya")
        self.type('input[name="last_name"]', "Rao")
        self.type('input[name="email"]', "maya@example.com")
        self.type('input[name="phone"]', "+919998887776")
        self.select_option_by_value('select[name="relation"]', "MO")
        self.click('dialog button:contains("Save")')
        self.assert_text("Link sent to maya@example.com")
        guardianship = Guardianship.objects.get(player=kid)
        self.assertEqual("maya@example.com", guardianship.user.email)
        self.assertEqual("MO", guardianship.relation)

    def test_the_same_guardian_says_updated_not_sent(self) -> None:
        kid = self.minor_with_guardian()
        self.sign_in_as(kid.user)
        self.open(f"{APP_URL}/waiver/{kid.id}")
        self.click(f"#guardian-change-{kid.id} button")
        self.type('input[name="first_name"]', "Senthil")
        self.type('input[name="last_name"]', "J")
        self.type('input[name="email"]', "Senthil@Example.com")
        self.type('input[name="phone"]', "+919998887776")
        self.select_option_by_value('select[name="relation"]', "FA")
        self.click('dialog button:contains("Save")')
        self.assert_text("Guardian updated")
        self.assertEqual("FA", Guardianship.objects.get(player=kid).relation)

    def test_a_minor_with_no_guardian_is_asked_to_add_one(self) -> None:
        kid = self.minor_with_guardian()
        Guardianship.objects.filter(player=kid).delete()
        self.sign_in_as(kid.user)
        self.set_window_size(390, 844)
        self.open(f"{APP_URL}/code-of-conduct/{kid.id}")
        self.assert_text("No guardian yet", f"#guardian-card-{kid.id}")
        self.assert_element_absent('button:contains("I agree")')

    def test_a_minor_who_is_their_own_guardian_is_asked_to_change_it(self) -> None:
        kid = self.minor_with_guardian()
        Guardianship.objects.filter(player=kid).update(user=kid.user)
        self.sign_in_as(kid.user)
        self.set_window_size(390, 844)
        self.open(f"{APP_URL}/waiver/{kid.id}")
        self.assert_text("Please change the guardian", f"#guardian-card-{kid.id}")
        self.assert_element_absent("form:not(dialog form) button[type=submit]")

    def test_a_guardian_signs_from_the_link(self) -> None:
        kid = self.minor_with_guardian()
        g = Guardianship.objects.get(player=kid)
        emails.send_link(g)
        self.set_window_size(390, 844)
        self.open(DJANGO_URL)  # production serves the page itself, which sets the CSRF cookie
        self.open(f"{APP_URL}/guardian/{tokens.mint(g)}")
        self.assert_text("Sign Tara's waiver")
        self.assert_text("Senthil J")
        self.click("#guardian-continue")
        self.assert_text("Waiver")
        self.click("#waiver")
        self.click("#legal")
        self.click('button:contains("I Agree")')
        self.assert_text("Next: agree to the code of conduct")

    def test_an_expired_link_offers_sign_in(self) -> None:
        kid = self.minor_with_guardian()
        g = Guardianship.objects.get(player=kid)
        emails.send_link(g)
        token = tokens.mint(g)
        Guardianship.objects.filter(pk=g.pk).update(
            link_sent_at=timezone.now() + datetime.timedelta(seconds=1)
        )
        self.open(f"{APP_URL}/guardian/{token}")
        self.assert_text("This link has expired or was already used.")
        href = self.get_attribute("#guardian-sign-in", "href")
        self.assertTrue(href.endswith(f"/login?redirect=/waiver/{kid.id}"), href)

    def test_i_agree_says_which_box_to_tick(self) -> None:
        kid = self.minor_with_guardian()
        self.sign_in_as(Guardianship.objects.get(player=kid).user)
        self.set_window_size(390, 844)
        self.open(f"{APP_URL}/waiver/{kid.id}")
        self.click('button:contains("I Agree")')
        self.assert_text("Tick this to continue")
        self.assertEqual("waiver", self.execute_script("return document.activeElement.id"))
        self.click("#waiver")
        self.assert_element_absent('p[role="alert"]:contains("Tick this to continue")')
        self.click('button:contains("I Agree")')
        self.assertEqual("legal", self.execute_script("return document.activeElement.id"))

    def test_a_team_admin_reminds_a_waiver(self) -> None:
        p = self.player("Dev", "Menon")
        Subscription.objects.filter(player=p).update(waiver_valid=False)
        self.sign_in_as(self.admin)
        self.open_page()
        self.click(f'{row("Dev")}//button[contains(., "Remind")]')
        self.assert_text("Reminder sent")
        self.assertEqual(1, Task.objects.filter(type=Task.TaskType.SEND_EMAIL).count())

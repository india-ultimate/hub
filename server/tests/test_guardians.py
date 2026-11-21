import datetime
import time
from unittest import mock

from dateutil.relativedelta import relativedelta
from django.test import Client, TestCase
from django.utils.timezone import now

from server.core.models import Guardianship, Player, Team, User
from server.guardians import access, emails, tokens
from server.tests.test_code_of_conduct import ADULT, minor_dob, person, subscribe


def linked(minor: Player, guardian_user: User) -> Guardianship:
    return Guardianship.objects.create(
        user=guardian_user, player=minor, relation="LG", link_sent_at=now()
    )


class TestToken(TestCase):
    def setUp(self) -> None:
        self.minor = person("kid@example.com", born=minor_dob(), first="Tara")
        self.parent = person("mum@example.com", born=ADULT, first="Mum")
        self.g = linked(self.minor, self.parent.user)

    def test_a_fresh_link_is_usable(self) -> None:
        self.assertEqual((self.g, True), tokens.inspect(tokens.mint(self.g)))

    def test_a_link_expires_after_7_days(self) -> None:
        token = tokens.mint(self.g)
        with mock.patch("django.core.signing.time.time", return_value=time.time() + 7 * 86400 + 1):
            self.assertEqual((self.g, False), tokens.inspect(token))

    def test_resend_kills_the_old_link(self) -> None:
        token = tokens.mint(self.g)
        self.g.link_sent_at = now() + datetime.timedelta(seconds=1)
        self.g.save()
        self.assertEqual((self.g, False), tokens.inspect(token))

    def test_a_new_guardian_kills_the_old_link(self) -> None:
        token = tokens.mint(self.g)
        self.g.user = person("dad@example.com", born=ADULT, first="Dad").user
        self.g.save()
        self.assertEqual((self.g, False), tokens.inspect(token))

    def test_finishing_both_steps_kills_the_link(self) -> None:
        sub = subscribe(self.minor)
        token = tokens.mint(self.g)
        sub.waiver_valid = True
        sub.save()
        self.assertEqual((self.g, True), tokens.inspect(token))
        sub.coc_agreed = True
        sub.save()
        self.assertEqual((self.g, False), tokens.inspect(token))

    def test_no_subscription_still_works(self) -> None:
        self.assertEqual((self.g, True), tokens.inspect(tokens.mint(self.g)))

    def test_a_ward_who_turned_18_has_no_link(self) -> None:
        token = tokens.mint(self.g)
        self.minor.date_of_birth = ADULT
        self.minor.save()
        self.assertEqual((self.g, False), tokens.inspect(token))

    def test_a_player_who_is_their_own_guardian_has_no_link(self) -> None:
        token = tokens.mint(self.g)
        self.g.user = self.minor.user
        self.g.save()
        self.assertEqual((self.g, False), tokens.inspect(token))

    def test_a_link_without_a_send_stamp_is_dead(self) -> None:
        token = tokens.mint(self.g)
        self.g.link_sent_at = None
        self.g.save()
        self.assertEqual((self.g, False), tokens.inspect(token))

    def test_garbage_is_nothing(self) -> None:
        self.assertEqual((None, False), tokens.inspect("nope"))


class TestAccess(TestCase):
    def setUp(self) -> None:
        self.minor = person("kid@example.com", born=minor_dob(), first="Tara")
        self.parent = person("mum@example.com", born=ADULT, first="Mum")
        self.g = linked(self.minor, self.parent.user)

    def test_who_may_manage_a_minor_s_guardian(self) -> None:
        staff = User.objects.create(username="staff", is_staff=True)
        admin = person("coach@example.com", born=ADULT, first="Coach").user
        stranger = person("x@example.com", born=ADULT, first="X").user
        team = Team.objects.create(name="Tigers", slug="tigers")
        team.admins.add(admin)
        self.minor.teams.add(team)
        for user in (self.minor.user, self.parent.user, staff):
            self.assertTrue(access.may_manage_guardian(user, self.minor), user)
        for user in (admin, stranger):
            self.assertFalse(access.may_manage_guardian(user, self.minor), user)

    def test_nobody_manages_an_adult_s_guardian(self) -> None:
        adult = person("adult@example.com", born=ADULT)
        self.assertFalse(access.may_manage_guardian(adult.user, adult))

    def test_guardian_rights_end_at_18(self) -> None:
        self.assertEqual([self.g], list(access.wards_of(self.parent.user)))
        self.assertTrue(access.is_guardian_of(self.parent.user, self.minor))
        self.minor.date_of_birth = now().date() - relativedelta(years=18)
        self.minor.save()
        self.assertEqual([], list(access.wards_of(self.parent.user)))
        self.assertFalse(access.is_guardian_of(self.parent.user, self.minor))

    def test_the_minor_checks_agree_on_the_18th_birthday(self) -> None:
        self.minor.date_of_birth = now().date() - relativedelta(years=18)
        self.minor.save()
        self.assertEqual(
            access.is_guardian_of(self.parent.user, self.minor),
            access.wards_of(self.parent.user).exists(),
        )
        self.assertFalse(self.minor.is_minor)


class TestLinkEndpoints(TestCase):
    def setUp(self) -> None:
        self.minor = person("kid@example.com", born=minor_dob(), first="Tara")
        self.parent = person("mum@example.com", born=ADULT, first="Mum")
        self.g = linked(self.minor, self.parent.user)
        self.token = tokens.mint(self.g)
        self.url = f"/api/guardians/link/{self.token}"
        self.client = Client(enforce_csrf_checks=False)

    def test_opening_the_link_signs_nobody_in(self) -> None:
        r = self.client.get(self.url)
        body = r.json()
        self.assertEqual(200, r.status_code)
        self.assertTrue(body["valid"])
        self.assertNotEqual("mum@example.com", body["guardian_email_masked"])
        self.assertEqual(self.minor.id, body["player_id"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_signed_out_viewer_is_nobody(self) -> None:
        body = self.client.get(self.url).json()
        self.assertFalse(body["signed_in_as_guardian"])
        self.assertIsNone(body["signed_in_name"])

    def test_the_guardian_is_recognised_as_signed_in(self) -> None:
        self.client.force_login(self.parent.user)
        body = self.client.get(self.url).json()
        self.assertTrue(body["signed_in_as_guardian"])
        self.assertIsNone(body["signed_in_name"])

    def test_another_signed_in_user_is_named(self) -> None:
        self.client.force_login(self.minor.user)
        body = self.client.get(self.url).json()
        self.assertFalse(body["signed_in_as_guardian"])
        self.assertEqual("Tara Kumar", body["signed_in_name"])

    def test_continue_signs_the_guardian_in_and_goes_to_the_waiver(self) -> None:
        r = self.client.post(self.url)
        self.assertEqual(200, r.status_code)
        self.assertEqual({"redirect": f"/waiver/{self.minor.id}"}, r.json())
        self.assertEqual(str(self.parent.user.pk), self.client.session["_auth_user_id"])

    def test_continue_switches_a_signed_in_user(self) -> None:
        self.client.force_login(self.minor.user)
        self.client.post(self.url)
        self.assertEqual(str(self.parent.user.pk), self.client.session["_auth_user_id"])

    def test_two_siblings_in_a_row(self) -> None:
        other = person("kid2@example.com", born=minor_dob(), first="Sam")
        url_b = f"/api/guardians/link/{tokens.mint(linked(other, self.parent.user))}"
        self.assertEqual(200, self.client.post(self.url).status_code)
        r = self.client.get(url_b)
        self.assertTrue(r.json()["valid"])
        self.assertEqual(200, self.client.post(url_b).status_code)

    def test_staff_are_not_signed_in_by_a_link(self) -> None:
        self.parent.user.is_staff = True
        self.parent.user.save()
        self.assertEqual(403, self.client.post(self.url).status_code)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_superusers_are_not_signed_in_by_a_link(self) -> None:
        self.parent.user.is_superuser = True
        self.parent.user.save()
        self.assertEqual(403, self.client.post(self.url).status_code)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_an_inactive_guardian_is_not_signed_in(self) -> None:
        self.parent.user.is_active = False
        self.parent.user.save()
        r = self.client.post(self.url)
        self.assertEqual(410, r.status_code)
        self.assertEqual("This link has expired or was already used.", r.json()["message"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_continue_needs_csrf(self) -> None:
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(403, client.post(self.url).status_code)
        self.assertNotIn("_auth_user_id", client.session)

    def test_an_expired_link_offers_the_normal_sign_in(self) -> None:
        with mock.patch("django.core.signing.time.time", return_value=time.time() + 7 * 86400 + 1):
            body = self.client.get(self.url).json()
            r = self.client.post(self.url)
        self.assertFalse(body["valid"])
        self.assertEqual(self.minor.id, body["player_id"])
        self.assertNotEqual("mum@example.com", body["guardian_email_masked"])
        self.assertEqual(410, r.status_code)

    def test_a_forged_link_is_404(self) -> None:
        self.assertEqual(404, self.client.get("/api/guardians/link/forged").status_code)
        self.assertEqual(404, self.client.post("/api/guardians/link/forged").status_code)


class TestSendLink(TestCase):
    def setUp(self) -> None:
        self.minor = person("kid@example.com", born=minor_dob(), first="Tara")
        self.parent = person("mum@example.com", born=ADULT, first="Mum")
        self.g = Guardianship.objects.create(
            user=self.parent.user, player=self.minor, relation="LG"
        )

    def test_send_link_stamps_and_emails_the_guardian(self) -> None:
        with mock.patch("server.guardians.emails.queue_emails") as queue:
            emails.send_link(self.g)
        self.g.refresh_from_db()
        self.assertIsNotNone(self.g.link_sent_at)
        (messages,) = queue.call_args.args
        self.assertEqual(1, len(messages))
        self.assertEqual(["mum@example.com"], messages[0].to)
        self.assertEqual("Please sign Tara's waiver for India Ultimate", messages[0].subject)
        self.assertIn("/guardian/", messages[0].body)
        self.assertIn("7 days", messages[0].body)

    def test_may_send_waits_10_minutes(self) -> None:
        self.assertTrue(emails.may_send(self.g))
        self.g.link_sent_at = now()
        self.assertFalse(emails.may_send(self.g))
        self.g.link_sent_at = now() - datetime.timedelta(minutes=11)
        self.assertTrue(emails.may_send(self.g))

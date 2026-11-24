import datetime
import time
from typing import Any, cast
from unittest import mock

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils.timezone import now

import server.mcp.tools  # noqa: F401
from server.core.models import Guardianship, Player, Team, User
from server.guardians import access, emails, tokens
from server.mcp.auth import TokenInfo
from server.mcp.registry import ToolContext
from server.mcp.tools import developer, membership
from server.season.models import Season
from server.series.models import SeriesRosterInvitation
from server.series.utils import invitations_for, may_answer_for
from server.subscription.api import may_see
from server.subscription.emails import queue_confirmation
from server.tests.test_code_of_conduct import ADULT, html, minor_dob, person, subscribe
from server.tests.test_eligibility import make_series
from server.transaction.models import ManualTransaction, PaymentGateway
from server.transaction.utils import list_transactions_by_type


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
        self.assertEqual("This link has expired, or a newer link was sent.", r.json()["message"])
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

    def test_send_link_without_an_address_sends_nothing(self) -> None:
        User.objects.filter(pk=self.parent.user_id).update(email="mum")
        self.g.refresh_from_db()
        with mock.patch("server.guardians.emails.queue_emails") as queue:
            self.assertFalse(emails.send_link(self.g))
        queue.assert_not_called()

    def test_the_email_names_who_added_the_guardian_and_has_no_css_in_its_text(self) -> None:
        with mock.patch("server.guardians.emails.queue_emails") as queue:
            emails.send_link(self.g, by=self.minor.user)
        message = queue.call_args.args[0][0]
        self.assertIn("Tara Kumar has added you as Tara Kumar's guardian", message.body)
        self.assertNotIn("font-family", message.body)

    def test_may_send_waits_10_minutes(self) -> None:
        self.assertTrue(emails.may_send(self.g))
        self.g.link_sent_at = now()
        self.assertFalse(emails.may_send(self.g))
        self.g.link_sent_at = now() - datetime.timedelta(minutes=11)
        self.assertTrue(emails.may_send(self.g))


class TestGuardianApi(TestCase):
    def setUp(self) -> None:
        self.minor = person("kid@example.com", born=minor_dob(), first="Tara")
        self.parent = person("mum@example.com", born=ADULT, first="Mum", last="Rao")
        self.g = linked(self.minor, self.parent.user)
        self.url = f"/api/players/{self.minor.id}/guardian"
        self.client = Client()
        self.client.force_login(self.minor.user)

    def body(self, **over: str) -> dict[str, str]:
        return {
            "first_name": "Dad",
            "last_name": "Rao",
            "email": "Dad@Example.com ",
            "phone": "",
            "relation": "FA",
        } | over

    def put(self, **over: str) -> Any:
        return self.client.put(self.url, self.body(**over), content_type="application/json")

    def test_the_minor_sees_their_guardian_with_the_full_email(self) -> None:
        r = self.client.get(self.url)
        self.assertEqual(200, r.status_code)
        g = r.json()["guardian"]
        self.assertEqual("mum@example.com", g["email"])
        self.assertEqual("Mum Rao", g["name"])
        self.assertEqual("LG", g["relation"])
        self.assertFalse(g["is_minor"])
        self.assertFalse(g["is_self"])
        self.assertTrue(r.json()["can_change"])
        self.assertTrue(r.json()["can_resend"])
        self.assertIsNone(r.json()["waiver"])

    def test_status_shows_who_signed(self) -> None:
        sub = subscribe(self.minor)
        sub.waiver_valid = True
        sub.waiver_signed_by = self.parent.user
        sub.waiver_signed_at = now()
        sub.save()
        body = self.client.get(self.url).json()
        self.assertTrue(body["waiver"]["done"])
        self.assertEqual("Mum Rao", body["waiver"]["by_name"])
        self.assertFalse(body["coc"]["done"])

    def test_a_failing_email_does_not_undo_the_change(self) -> None:
        with mock.patch("server.guardians.emails.queue_emails", side_effect=RuntimeError):
            r = self.put()
        self.assertEqual(200, r.status_code)
        self.assertEqual("dad@example.com", Guardianship.objects.get(player=self.minor).user.email)

    def test_a_team_admin_cannot_see_or_change_the_guardian(self) -> None:
        admin = person("coach@example.com", born=ADULT, first="Coach").user
        team = Team.objects.create(name="Tigers", slug="tigers")
        team.admins.add(admin)
        self.minor.teams.add(team)
        self.client.force_login(admin)
        self.assertEqual(403, self.client.get(self.url).status_code)
        self.assertEqual(403, self.put().status_code)

    def test_nobody_sees_an_adult_s_guardian(self) -> None:
        adult = person("adult@example.com", born=ADULT)
        self.client.force_login(adult.user)
        self.assertEqual(403, self.client.get(f"/api/players/{adult.id}/guardian").status_code)

    def test_unknown_player_is_404(self) -> None:
        self.assertEqual(404, self.client.get("/api/players/999999/guardian").status_code)

    def test_changing_the_guardian_keeps_what_the_old_one_signed(self) -> None:
        sub = subscribe(self.minor)
        sub.waiver_valid = sub.coc_agreed = True
        sub.waiver_signed_by = sub.coc_agreed_by = self.parent.user
        sub.save()
        with mock.patch("server.guardians.emails.queue_emails"):
            self.assertEqual(200, self.put().status_code)
        sub.refresh_from_db()
        self.assertTrue(sub.waiver_valid and sub.coc_agreed)
        self.assertEqual(self.parent.user, sub.waiver_signed_by)
        self.assertEqual(self.parent.user, sub.coc_agreed_by)

    def test_changing_the_guardian_emails_both_people(self) -> None:
        with mock.patch("server.guardians.emails.queue_emails") as queue:
            r = self.put()
        self.assertEqual(200, r.status_code)
        self.assertEqual("dad@example.com", r.json()["guardian"]["email"])
        self.assertEqual(1, Guardianship.objects.count())
        sent = {m.to[0]: m for call in queue.call_args_list for m in call.args[0]}
        self.assertIn("/guardian/", sent["dad@example.com"].body)
        self.assertEqual("Tara's guardian was changed", sent["mum@example.com"].subject)
        self.assertIn("Tara changed their guardian to Dad Rao.", sent["mum@example.com"].body)

    def test_a_minor_cannot_be_a_guardian(self) -> None:
        person("teen@example.com", born=minor_dob(), first="Teen")
        r = self.put(email="teen@example.com")
        self.assertEqual(400, r.status_code)
        self.assertEqual(
            "A guardian must be 18 or older. Please use a parent or another adult.",
            r.json()["message"],
        )
        self.g.refresh_from_db()
        self.assertEqual(self.parent.user, self.g.user)

    def test_a_refused_address_leaves_no_account(self) -> None:
        before = User.objects.count()
        self.put(email="nobody")
        self.put(email="kid@example.com")
        self.assertEqual(before, User.objects.count())

    def test_a_player_cannot_be_their_own_guardian(self) -> None:
        r = self.put(email="kid@example.com")
        self.assertEqual(400, r.status_code)
        self.assertEqual(
            "That's Tara's own account. A guardian needs their own email.", r.json()["message"]
        )

    def test_an_address_without_at_is_refused(self) -> None:
        r = self.put(email="nobody")
        self.assertEqual(400, r.status_code)
        self.assertEqual("Enter a valid email address", r.json()["message"])

    def test_same_guardian_changes_only_the_relation(self) -> None:
        with mock.patch("server.guardians.emails.queue_emails") as queue:
            r = self.put(email="mum@example.com", relation="FA")
        self.assertEqual(200, r.status_code)
        queue.assert_not_called()
        self.g.refresh_from_db()
        self.assertEqual("FA", self.g.relation)

    def test_resend_waits_10_minutes(self) -> None:
        self.g.link_sent_at = None
        self.g.save()
        with mock.patch("server.guardians.emails.queue_emails"):
            first = self.client.post(f"{self.url}/link")
            second = self.client.post(f"{self.url}/link")
            self.assertEqual(200, first.status_code)
            self.assertEqual("Link sent to mum@example.com", first.json()["message"])
            self.assertEqual(429, second.status_code)
            self.g.refresh_from_db()
            self.g.link_sent_at = now() - datetime.timedelta(minutes=11)
            self.g.save()
            self.assertEqual(200, self.client.post(f"{self.url}/link").status_code)

    def test_resend_kills_the_link_already_sent(self) -> None:
        self.g.link_sent_at = now() - datetime.timedelta(minutes=11)
        self.g.save()
        old = tokens.mint(self.g)
        with mock.patch("server.guardians.emails.queue_emails"):
            self.assertEqual(200, self.client.post(f"{self.url}/link").status_code)
        self.assertFalse(tokens.inspect(old)[1])

    def test_resend_says_so_when_there_is_no_address(self) -> None:
        self.g.link_sent_at = None
        self.g.save()
        User.objects.filter(pk=self.parent.user_id).update(email="mum")
        with mock.patch("server.guardians.emails.queue_emails") as queue:
            r = self.client.post(f"{self.url}/link")
        self.assertEqual(400, r.status_code)
        queue.assert_not_called()

    def test_a_failing_resend_is_not_a_500_and_keeps_the_old_link(self) -> None:
        self.g.link_sent_at = None
        self.g.save()
        with mock.patch("server.guardians.emails.queue_emails", side_effect=RuntimeError):
            r = self.client.post(f"{self.url}/link")
        self.assertEqual(400, r.status_code)
        self.g.refresh_from_db()
        self.assertIsNone(self.g.link_sent_at)

    def test_resend_needs_a_guardian_who_is_not_the_player(self) -> None:
        self.g.user = self.minor.user
        self.g.save()
        self.assertEqual(400, self.client.post(f"{self.url}/link").status_code)
        self.g.delete()
        self.assertEqual(400, self.client.post(f"{self.url}/link").status_code)

    def test_the_status_of_a_ward_with_no_subscription_has_no_waiver(self) -> None:
        body = self.client.get(self.url).json()
        self.assertIsNone(body["waiver"])
        self.assertIsNone(body["coc"])
        self.assertEqual("Mum", body["guardian"]["first_name"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_a_player_may_change_the_guardian_three_times_an_hour(self) -> None:
        cache.clear()
        with mock.patch("server.guardians.emails.queue_emails"):
            for n in range(3):
                self.assertEqual(200, self.put(email=f"dad{n}@example.com").status_code)
            self.assertEqual(200, self.put(email="dad2@example.com", relation="MO").status_code)
            r = self.put(email="dad3@example.com")
        self.assertEqual(429, r.status_code)
        self.assertIn("Try again in an hour", r.json()["message"])
        self.assertEqual("dad2@example.com", Guardianship.objects.get(player=self.minor).user.email)

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_staff_are_not_capped(self) -> None:
        cache.clear()
        User.objects.filter(pk=self.minor.user_id).update(is_staff=True)
        with mock.patch("server.guardians.emails.queue_emails"):
            for n in range(5):
                self.assertEqual(200, self.put(email=f"dad{n}@example.com").status_code)

    def test_a_change_retires_the_old_stamp_even_if_the_email_fails(self) -> None:
        with mock.patch("server.guardians.emails.queue_emails", side_effect=RuntimeError):
            self.assertEqual(200, self.put().status_code)
        g = Guardianship.objects.get(player=self.minor)
        self.assertIsNone(g.link_sent_at)

    def test_a_minor_with_no_guardian_adds_one(self) -> None:
        self.g.delete()
        self.assertIsNone(self.client.get(self.url).json()["guardian"])
        with mock.patch("server.guardians.emails.queue_emails") as queue:
            r = self.put()
        self.assertEqual(200, r.status_code)
        self.assertEqual(1, queue.call_count)
        self.assertEqual(["dad@example.com"], queue.call_args.args[0][0].to)


GUARDIAN_FORM = {
    "phone": "+1234567890",
    "gender": "F",
    "match_up": "F",
    "city": "Bangalore",
    "first_name": "Nora",
    "last_name": "Quinn",
    "guardian_first_name": "Mora",
    "guardian_last_name": "Saiyyan",
    "guardian_email": "mora@gmail.com",
    "guardian_phone": "+123321456654",
    "relation": "MO",
}


class TestRegistration(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="nora@example.com", email="nora@example.com")
        self.client = Client()
        self.client.force_login(self.user)

    def form(self, born: datetime.date | None = None) -> dict[str, str]:
        return {**GUARDIAN_FORM, "date_of_birth": str(born or minor_dob())}

    def post(self, path: str, data: dict[str, str]) -> Any:
        return self.client.post(path, data=data, content_type="application/json")

    def test_register_guardian_leaves_no_orphan_account(self) -> None:
        Player.objects.create(user=self.user, date_of_birth=minor_dob())
        r = self.post("/api/registration/guardian", self.form())
        self.assertEqual(400, r.status_code)
        self.assertIn("already registered", r.json()["message"])
        self.assertFalse(User.objects.filter(email="mora@gmail.com").exists())

    def test_a_refused_minor_registration_creates_no_guardian_account(self) -> None:
        r = self.post("/api/registration/guardian", self.form(born=ADULT))
        self.assertEqual(400, r.status_code)
        self.assertFalse(User.objects.filter(email="mora@gmail.com").exists())

    def test_register_guardian_emails_the_guardian_a_link(self) -> None:
        with mock.patch("server.guardians.emails.queue_emails") as queue:
            r = self.post("/api/registration/guardian", self.form())
        self.assertEqual(200, r.status_code)
        self.assertEqual(["mora@gmail.com"], queue.call_args.args[0][0].to)
        self.assertIsNotNone(Guardianship.objects.get(player__user=self.user).link_sent_at)

    def test_register_ward_for_an_existing_player_says_to_ask_them(self) -> None:
        ward = person("kid@example.com", born=minor_dob(), first="Tara")
        data = {**self.form(), "email": ward.user.email}
        data.pop("guardian_email")
        r = self.post("/api/registration/ward", data)
        self.assertEqual(400, r.status_code)
        self.assertEqual(
            "Tara already has a hub account. Ask them to add you as guardian from their profile.",
            r.json()["message"],
        )

    def test_a_refused_ward_registration_creates_no_ward_account(self) -> None:
        r = self.post(
            "/api/registration/ward", {**self.form(born=ADULT), "email": "kid@example.com"}
        )
        self.assertEqual(400, r.status_code)
        self.assertFalse(User.objects.filter(email="kid@example.com").exists())

    def test_a_minor_cannot_be_the_guardian(self) -> None:
        person("kid2@example.com", born=minor_dob())
        r = self.post(
            "/api/registration/guardian", {**self.form(), "guardian_email": "kid2@example.com"}
        )
        self.assertEqual(400, r.status_code)
        self.assertEqual(
            "A guardian must be 18 or older. Please use a parent or another adult.",
            r.json()["message"],
        )
        self.assertFalse(Player.objects.filter(user=self.user).exists())

    def test_a_failing_guardian_email_does_not_undo_the_registration(self) -> None:
        with mock.patch("server.guardians.emails.queue_emails", side_effect=RuntimeError):
            r = self.post("/api/registration/guardian", self.form())
        self.assertEqual(200, r.status_code)
        self.assertTrue(Player.objects.filter(user=self.user).exists())


class TestConfirmation(TestCase):
    def setUp(self) -> None:
        self.minor = person("kid@example.com", born=minor_dob(), first="Tara")
        self.parent = person("mum@example.com", born=ADULT, first="Mum")
        self.g = Guardianship.objects.create(
            user=self.parent.user, player=self.minor, relation="MO"
        )
        self.sub = subscribe(self.minor)

    def confirm(self) -> list[Any]:
        with (
            mock.patch("server.guardians.emails.queue_emails") as link,
            mock.patch("server.subscription.emails.queue_emails") as confirmation,
        ):
            queue_confirmation(self.sub)
        return [link, confirmation]

    def test_a_minor_s_subscription_emails_the_guardian(self) -> None:
        link, confirmation = self.confirm()
        self.assertEqual(["mum@example.com"], link.call_args.args[0][0].to)
        self.assertIn("We've emailed Mum Kumar", html(confirmation.call_args.args[0][0]))

    def test_a_guardian_without_an_at_address_is_not_claimed_emailed(self) -> None:
        self.parent.user.email = "mum-rao"
        self.parent.user.save()
        _, confirmation = self.confirm()
        body = html(confirmation.call_args.args[0][0])
        self.assertNotIn("We've emailed", body)
        self.assertIn("Sign the waiver", body)

    def test_a_minor_without_an_at_address_still_gets_the_guardian_link(self) -> None:
        self.minor.user.email = "tara-kumar"
        self.minor.user.save()
        link, confirmation = self.confirm()
        self.assertEqual(1, link.call_count)
        self.assertEqual(0, confirmation.call_count)

    def test_no_second_link_within_10_minutes(self) -> None:
        self.confirm()
        link, _ = self.confirm()
        self.assertEqual(0, link.call_count)

    def test_the_confirmation_keeps_the_registration_link_valid(self) -> None:
        self.g.link_sent_at = now() - datetime.timedelta(minutes=11)
        self.g.save()
        token = tokens.mint(self.g)
        link, _ = self.confirm()
        self.assertEqual(1, link.call_count)
        self.assertTrue(tokens.inspect(token)[1])

    def test_a_failing_guardian_email_does_not_fail_the_confirmation(self) -> None:
        with (
            mock.patch("server.guardians.emails.queue_emails", side_effect=RuntimeError),
            mock.patch("server.subscription.emails.queue_emails") as confirmation,
        ):
            queue_confirmation(self.sub)
        self.assertEqual(1, confirmation.call_count)


class TestRightsEndAt18(TestCase):
    def setUp(self) -> None:
        self.minor = person("kid@example.com", born=minor_dob(), first="Tara")
        self.parent = person("mum@example.com", born=ADULT, first="Mum")
        self.g = linked(self.minor, self.parent.user)
        self.guardian = self.parent.user

    def turn(self, days: int = 0) -> None:
        self.minor.date_of_birth = (
            now().date() - relativedelta(years=18) + datetime.timedelta(days=days)
        )
        self.minor.save()

    def ctx(self) -> ToolContext:
        return ToolContext(
            user=self.guardian,
            token=TokenInfo(self.guardian, frozenset({"hub:write"}), "client"),
            modern=True,
            client_capabilities={},
            input_responses=None,
            request_state=None,
            tool_name="x",
            outer=RequestFactory().post("/mcp"),
        )

    def test_may_see(self) -> None:
        self.turn(1)
        self.assertTrue(may_see(self.guardian, self.minor))
        self.turn()
        self.assertFalse(may_see(self.guardian, self.minor))

    def test_dashboard_wards(self) -> None:
        client = Client()
        client.force_login(self.guardian)
        self.assertEqual([self.minor.id], [w["id"] for w in client.get("/api/me").json()["wards"]])
        self.turn()
        self.assertEqual([], client.get("/api/me").json()["wards"])

    def test_series_answers(self) -> None:
        series = make_series(Season.objects.get(name="Season 2026-2027"))
        team = Team.objects.create(name="Team A")
        invitation = SeriesRosterInvitation.objects.create(
            series=series, team=team, from_user=self.guardian, to_player=self.minor
        )
        self.assertTrue(may_answer_for(self.guardian, self.minor))
        self.assertEqual([invitation], list(invitations_for(self.guardian)))
        self.turn()
        self.assertFalse(may_answer_for(self.guardian, self.minor))
        self.assertEqual([], list(invitations_for(self.guardian)))

    def test_mcp_membership(self) -> None:
        self.assertIn(self.minor.id, membership._own_ids(self.ctx()))
        self.turn()
        self.assertNotIn(self.minor.id, membership._own_ids(self.ctx()))

    def test_mcp_see_player(self) -> None:
        self.assertTrue(developer._see_player(self.guardian, str(self.minor.id))[0])
        self.turn()
        self.assertFalse(developer._see_player(self.guardian, str(self.minor.id))[0])

    def test_signed_waiver_stays_valid(self) -> None:
        sub = subscribe(self.minor)
        client = Client()
        client.force_login(self.guardian)
        r = client.post(
            "/api/waiver", {"player_id": self.minor.id}, content_type="application/json"
        )
        self.assertEqual(200, r.status_code, r.content)
        self.turn()
        sub.refresh_from_db()
        self.assertTrue(sub.waiver_valid)

    def test_transactions(self) -> None:
        paid_by_ward = ManualTransaction.objects.create(
            transaction_id="W1", amount=100, user=self.minor.user
        )
        paid_by_ward.players.add(self.minor)
        paid_by_guardian = ManualTransaction.objects.create(
            transaction_id="G1", amount=100, user=self.guardian
        )

        def seen() -> set[str]:
            return {
                cast(ManualTransaction, t).transaction_id
                for t in list_transactions_by_type(self.guardian, PaymentGateway.MANUAL)
            }

        self.assertEqual({"W1", "G1"}, seen())
        self.turn()
        self.assertEqual({paid_by_guardian.transaction_id}, seen())

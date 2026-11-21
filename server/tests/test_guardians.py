import datetime
import time
from unittest import mock

from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils.timezone import now

from server.core.models import Guardianship, Player, Team, User
from server.guardians import access, tokens
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

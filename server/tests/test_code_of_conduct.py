"""Agreeing to the code of conduct, once a season, like the waiver."""

import datetime
from typing import Any

from django.core.mail import EmailMultiAlternatives
from django.test import Client, TestCase

from server.core.models import Guardianship, Player, User
from server.season.models import Season
from server.subscription.emails import build_confirmation
from server.subscription.models import Subscription
from server.utils import today

URL = "/api/code-of-conduct"


def person(email: str, *, born: datetime.date, first: str = "Ravi", last: str = "Kumar") -> Player:
    user = User.objects.create(username=email, email=email, first_name=first, last_name=last)
    return Player.objects.create(user=user, date_of_birth=born)


def subscribe(player: Player, season: Season | None = None) -> Subscription:
    season = season or Season.current()
    assert season is not None  # noqa: S101 - the seeded seasons cover today
    return Subscription.objects.create(
        player=player,
        season=season,
        start_date=season.start_date,
        end_date=season.end_date,
        is_active=True,
    )


ADULT = datetime.date(1995, 6, 15)


def html(message: EmailMultiAlternatives) -> str:
    return str(message.alternatives[0][0])


def minor_dob() -> datetime.date:
    return today() - datetime.timedelta(days=15 * 365)


class TestAgreeing(TestCase):
    def setUp(self) -> None:
        self.adult = person("ravi@example.com", born=ADULT)
        self.subscription = subscribe(self.adult)

    def post(self, user: User, player: Player) -> tuple[int, dict[str, Any]]:
        client = Client()
        client.force_login(user)
        response = client.post(URL, {"player_id": player.id}, content_type="application/json")
        return response.status_code, response.json()

    def test_an_adult_agrees_for_themselves(self) -> None:
        status, body = self.post(self.adult.user, self.adult)
        self.assertEqual(200, status, body)
        self.assertTrue(body["subscription"]["coc_agreed"])
        self.assertEqual("Ravi Kumar", body["subscription"]["coc_agreed_by"])
        self.assertIsNotNone(body["subscription"]["coc_agreed_at"])
        self.subscription.refresh_from_db()
        self.assertEqual(self.adult.user, self.subscription.coc_agreed_by)

    def test_nobody_else_agrees_for_an_adult(self) -> None:
        other = person("dev@example.com", born=ADULT, first="Dev")
        status, body = self.post(other.user, self.adult)
        self.assertEqual(400, status)
        self.assertEqual("Only Ravi Kumar can agree to their code of conduct", body["message"])
        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.coc_agreed)

    def test_a_guardian_agrees_for_a_minor(self) -> None:
        minor = person("kid@example.com", born=minor_dob(), first="Tara")
        sub = subscribe(minor)
        Guardianship.objects.create(user=self.adult.user, player=minor, relation="MO")
        status, body = self.post(self.adult.user, minor)
        self.assertEqual(200, status, body)
        sub.refresh_from_db()
        self.assertTrue(sub.coc_agreed)
        self.assertEqual(self.adult.user, sub.coc_agreed_by)

    def test_a_minor_cannot_agree_for_themselves(self) -> None:
        minor = person("kid@example.com", born=minor_dob(), first="Tara")
        subscribe(minor)
        Guardianship.objects.create(user=self.adult.user, player=minor, relation="MO")
        status, body = self.post(minor.user, minor)
        self.assertEqual(400, status)
        self.assertEqual("Only your guardian can agree for you", body["message"])

    def test_someone_who_is_not_the_guardian_cannot_agree_for_a_minor(self) -> None:
        minor = person("kid@example.com", born=minor_dob(), first="Tara")
        subscribe(minor)
        Guardianship.objects.create(user=self.adult.user, player=minor, relation="MO")
        other = person("dev@example.com", born=ADULT, first="Dev")
        status, body = self.post(other.user, minor)
        self.assertEqual(400, status)
        self.assertEqual(
            f"Only {self.adult.user.username} can agree for this player", body["message"]
        )

    def test_no_subscription_is_refused(self) -> None:
        self.subscription.delete()
        status, body = self.post(self.adult.user, self.adult)
        self.assertEqual(400, status)
        self.assertEqual("Get this season's subscription first", body["message"])

    def test_agreeing_twice_keeps_the_first_record(self) -> None:
        self.post(self.adult.user, self.adult)
        self.subscription.refresh_from_db()
        first_at = self.subscription.coc_agreed_at
        status, _ = self.post(self.adult.user, self.adult)
        self.assertEqual(200, status)
        self.subscription.refresh_from_db()
        self.assertEqual(first_at, self.subscription.coc_agreed_at)

    def test_agreeing_marks_only_this_seasons_subscription(self) -> None:
        last = Season.objects.get(name="Season 2025-2026")
        old = subscribe(self.adult, last)
        self.post(self.adult.user, self.adult)
        old.refresh_from_db()
        self.assertFalse(old.coc_agreed)
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.coc_agreed)


class TestConfirmationEmail(TestCase):
    def test_the_confirmation_asks_for_the_code_of_conduct(self) -> None:
        player = person("ravi@example.com", born=ADULT)
        sub = subscribe(player)
        self.assertIn(f"/code-of-conduct/{player.id}", html(build_confirmation(sub)))
        sub.coc_agreed = True
        sub.save()
        self.assertNotIn("/code-of-conduct/", html(build_confirmation(sub)))

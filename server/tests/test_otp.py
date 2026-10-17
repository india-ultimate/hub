import datetime
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest import mock

import pyotp
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from server.api import get_email_hash
from server.core.models import OTPAttempt, User


@contextmanager
def at(moment: datetime.datetime) -> Iterator[None]:
    """Every clock the OTP endpoints and their rows read, set to `moment`."""
    with (
        mock.patch("django.utils.timezone.now", return_value=moment),
        mock.patch("server.api.now", return_value=moment),
    ):
        yield


class OTPTestCase(TestCase):
    def send(self, email: str, ip: str = "10.0.0.1") -> Any:
        return self.client.post(
            "/api/send-otp",
            data=json.dumps({"email": email}),
            content_type="application/json",
            HTTP_FLY_CLIENT_IP=ip,
        )

    def guess(self, email: str, otp: str, ts: int | None = None, ip: str = "10.0.0.1") -> Any:
        ts = int(timezone.now().timestamp()) if ts is None else ts
        return self.client.post(
            "/api/otp-login",
            data=json.dumps({"email": email, "otp": otp, "otp_ts": ts}),
            content_type="application/json",
            HTTP_FLY_CLIENT_IP=ip,
        )

    def code(self, email: str, ts: int) -> str:
        return pyotp.TOTP(get_email_hash(email)).generate_otp(ts)

    def wrong(self, email: str, ts: int) -> str:
        return f"{(int(self.code(email, ts)) + 1) % 1_000_000:06d}"

    def assert_too_many(self, response: Any) -> None:
        self.assertEqual(response.status_code, 429, response.content)
        self.assertRegex(
            response.json()["message"], r"^Too many attempts\. Try again in \d+ minutes?\.$"
        )


class TestSendLimits(OTPTestCase):
    def test_the_fourth_send_to_an_email_in_ten_minutes_is_refused_and_sends_nothing(self) -> None:
        for _ in range(3):
            self.assertEqual(self.send("a@x.com").status_code, 200)
        self.assertEqual(len(mail.outbox), 3)

        response = self.send("a@x.com")

        self.assert_too_many(response)
        self.assertEqual(response.json()["message"], "Too many attempts. Try again in 10 minutes.")
        self.assertEqual(len(mail.outbox), 3)

    def test_the_eleventh_send_to_an_email_in_an_hour_is_refused_from_any_ip(self) -> None:
        start = timezone.now()
        for i in range(10):
            with at(start + datetime.timedelta(minutes=i)):
                self.assertEqual(self.send("a@x.com", ip=f"10.1.0.{i}").status_code, 200)
        with at(start + datetime.timedelta(minutes=10)):
            response = self.send("a@x.com", ip="10.1.1.1")
        self.assert_too_many(response)
        # The first send ages out an hour after it was made.
        self.assertEqual(response.json()["message"], "Too many attempts. Try again in 50 minutes.")
        self.assertEqual(len(mail.outbox), 10)
        # There is no daily cap.
        with at(start + datetime.timedelta(hours=1, seconds=1)):
            self.assertEqual(self.send("a@x.com", ip="10.1.1.1").status_code, 200)

    def test_a_strangers_sends_from_another_ip_do_not_stop_the_owners(self) -> None:
        for _ in range(3):
            self.send("a@x.com", ip="10.6.6.6")
        self.assert_too_many(self.send("a@x.com", ip="10.6.6.6"))

        self.assertEqual(self.send("a@x.com").status_code, 200)

    def test_gmail_dot_variants_share_one_email_limit(self) -> None:
        for email in ("victim@gmail.com", "v.ictim@gmail.com", "V..I.ctim@Gmail.com"):
            self.assertEqual(self.send(email).status_code, 200)

        self.assert_too_many(self.send("vic.tim@gmail.com"))

    def test_ipv6_addresses_in_one_slash_64_share_the_ip_limit(self) -> None:
        for i in range(20):
            self.assertEqual(
                self.send(f"p{i}@x.com", ip=f"2001:db8:1:2::{i + 1:x}").status_code, 200
            )

        self.assert_too_many(self.send("fresh@x.com", ip="2001:db8:1:2:ffff:ffff:ffff:fffe"))
        self.assertEqual(self.send("fresh@x.com", ip="2001:db8:1:3::1").status_code, 200)
        # IPv4 is not bucketed.
        for i in range(20):
            self.send(f"q{i}@x.com", ip="10.2.0.1")
        self.assertEqual(self.send("fresh2@x.com", ip="10.2.0.2").status_code, 200)

    def test_the_twenty_first_send_from_an_ip_in_an_hour_is_refused_across_emails(self) -> None:
        for i in range(20):
            self.assertEqual(self.send(f"p{i}@x.com", ip="10.9.9.9").status_code, 200)

        self.assert_too_many(self.send("fresh@x.com", ip="10.9.9.9"))
        self.assertEqual(len(mail.outbox), 20)
        # Another address from another IP is unaffected.
        self.assertEqual(self.send("fresh@x.com", ip="10.8.8.8").status_code, 200)

    def test_a_client_sent_forwarded_for_does_not_dodge_the_ip_limit(self) -> None:
        for i in range(20):
            self.client.post(
                "/api/send-otp",
                data=json.dumps({"email": f"p{i}@x.com"}),
                content_type="application/json",
                HTTP_FLY_CLIENT_IP="10.9.9.9",
                HTTP_X_FORWARDED_FOR=f"192.168.0.{i}",
            )
        self.assert_too_many(
            self.client.post(
                "/api/send-otp",
                data=json.dumps({"email": "fresh@x.com"}),
                content_type="application/json",
                HTTP_FLY_CLIENT_IP="10.9.9.9",
                HTTP_X_FORWARDED_FOR="192.168.1.1",
            )
        )

    def test_the_window_resets_once_ten_minutes_pass(self) -> None:
        start = timezone.now()
        with at(start):
            for _ in range(3):
                self.send("a@x.com")
            self.assert_too_many(self.send("a@x.com"))
        with at(start + datetime.timedelta(minutes=9, seconds=1)):
            response = self.send("a@x.com")
            self.assertEqual(
                response.json()["message"], "Too many attempts. Try again in 1 minute."
            )
        with at(start + datetime.timedelta(minutes=10, seconds=1)):
            self.assertEqual(self.send("a@x.com").status_code, 200)


class TestGuessLimits(OTPTestCase):
    def test_the_sixth_guess_from_an_ip_for_an_email_is_refused_even_with_the_right_code(
        self,
    ) -> None:
        ts = int(timezone.now().timestamp())
        for _ in range(5):
            self.assertEqual(self.guess("a@x.com", self.wrong("a@x.com", ts), ts).status_code, 403)

        response = self.guess("a@x.com", self.code("a@x.com", ts), ts)

        self.assert_too_many(response)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_strangers_wrong_guesses_from_another_ip_do_not_block_the_owners_code(
        self,
    ) -> None:
        ts = int(timezone.now().timestamp())
        for _ in range(5):
            self.guess("a@x.com", self.wrong("a@x.com", ts), ts, ip="10.6.6.6")
        self.assert_too_many(self.guess("a@x.com", self.wrong("a@x.com", ts), ts, ip="10.6.6.6"))

        self.assertEqual(self.guess("a@x.com", self.code("a@x.com", ts), ts).status_code, 200)

    def test_the_thirty_first_guess_for_an_email_in_an_hour_is_refused_from_any_ip(self) -> None:
        ts = int(timezone.now().timestamp())
        for i in range(30):
            ip = f"10.1.0.{i // 5}"
            self.assertEqual(
                self.guess("a@x.com", self.wrong("a@x.com", ts), ts, ip=ip).status_code, 403
            )

        self.assert_too_many(self.guess("a@x.com", self.code("a@x.com", ts), ts, ip="10.1.1.1"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_gmail_dot_variants_share_one_email_limit(self) -> None:
        ts = int(timezone.now().timestamp())
        for i in range(5):
            email = "v" + "." * i + "ictim@gmail.com"
            self.assertEqual(self.guess(email, self.wrong(email, ts), ts).status_code, 403)

        email = "vi.ctim@gmail.com"
        self.assert_too_many(self.guess(email, self.code(email, ts), ts))

    def test_the_fifty_first_guess_from_an_ip_is_refused_across_emails(self) -> None:
        ts = int(timezone.now().timestamp())
        for i in range(50):
            email = f"p{i}@x.com"
            self.assertEqual(self.guess(email, self.wrong(email, ts), ts).status_code, 403)

        self.assert_too_many(self.guess("fresh@x.com", self.code("fresh@x.com", ts), ts))
        other = self.guess("fresh@x.com", self.code("fresh@x.com", ts), ts, ip="10.8.8.8")
        self.assertEqual(other.status_code, 200)

    def test_right_guesses_count_too(self) -> None:
        ts = int(timezone.now().timestamp())
        for _ in range(5):
            self.assertEqual(self.guess("a@x.com", self.code("a@x.com", ts), ts).status_code, 200)
        self.assert_too_many(self.guess("a@x.com", self.code("a@x.com", ts), ts))

    def test_guesses_arriving_while_others_verify_cannot_overshoot_the_limit(self) -> None:
        """Every other guess lands while the first is between its limit
        check and its verification, as concurrent requests can."""
        ts = int(timezone.now().timestamp())
        wrong = self.wrong("a@x.com", ts)
        generate = pyotp.TOTP.generate_otp
        pending, verified, responses = 11, 0, []

        def verify_while_others_arrive(totp: pyotp.TOTP, input: int) -> str:
            nonlocal pending, verified
            verified += 1
            while pending:
                pending -= 1
                responses.append(self.guess("a@x.com", wrong, ts))
            return generate(totp, input)

        with mock.patch.object(pyotp.TOTP, "generate_otp", verify_while_others_arrive):
            responses.append(self.guess("a@x.com", wrong, ts))

        self.assertEqual(verified, 5)
        self.assertEqual(sorted(r.status_code for r in responses), [403] * 5 + [429] * 7)

    def test_the_right_code_within_limits_signs_in(self) -> None:
        ts = self.send("a@x.com").json()["otp_ts"]
        self.guess("a@x.com", self.wrong("a@x.com", ts), ts)

        response = self.guess("a@x.com", self.code("a@x.com", ts), ts)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "a@x.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get().id)


class TestExpiry(OTPTestCase):
    expired = "This code has expired. Ask for a new one."

    def test_a_code_over_ten_minutes_old_is_refused(self) -> None:
        ts = int(timezone.now().timestamp()) - 601
        response = self.guess("a@x.com", self.code("a@x.com", ts), ts)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["message"], self.expired)

    # Both edge tests stop the clock: a second passing mid-request on a slow
    # machine would move the code to the other side of an edge.
    def test_a_code_from_the_future_is_refused(self) -> None:
        moment = timezone.now()
        ts = int(moment.timestamp()) + 31
        with at(moment):
            response = self.guess("a@x.com", self.code("a@x.com", ts), ts)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["message"], self.expired)

    def test_a_code_just_inside_both_edges_signs_in(self) -> None:
        moment = timezone.now()
        for offset in (-590, 25):
            self.client.logout()
            ts = int(moment.timestamp()) + offset
            with at(moment):
                response = self.guess("a@x.com", self.code("a@x.com", ts), ts)
            self.assertEqual(response.status_code, 200)


class TestPruning(OTPTestCase):
    def test_rows_over_an_hour_old_are_deleted_on_the_next_attempt(self) -> None:
        start = timezone.now()
        with at(start):
            self.send("old@x.com")
        with at(start + datetime.timedelta(minutes=59)):
            self.send("recent@x.com")
        with at(start + datetime.timedelta(hours=1, seconds=1)):
            self.send("new@x.com")

        self.assertEqual(
            sorted(OTPAttempt.objects.values_list("email", flat=True)),
            ["new@x.com", "recent@x.com"],
        )


class TestPasswordLimits(OTPTestCase):
    def setUp(self) -> None:
        user = User.objects.create(username="admin@x.com", email="admin@x.com")
        user.set_password("right")
        user.save()

    def log_in(self, password: str, ip: str = "10.0.0.1", username: str = "admin@x.com") -> Any:
        return self.client.post(
            "/api/login",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
            HTTP_FLY_CLIENT_IP=ip,
        )

    def test_the_eleventh_failure_from_an_ip_is_refused_even_with_the_right_password(
        self,
    ) -> None:
        for _ in range(10):
            self.assertEqual(self.log_in("wrong").status_code, 403)

        self.assert_too_many(self.log_in("right"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_strangers_failures_from_another_ip_do_not_block_the_owner(self) -> None:
        for _ in range(10):
            self.log_in("wrong", ip="10.6.6.6")
        self.assert_too_many(self.log_in("wrong", ip="10.6.6.6"))

        self.assertEqual(self.log_in("right").status_code, 200)

    def test_the_fifty_first_failure_for_a_username_in_an_hour_is_refused_from_any_ip(
        self,
    ) -> None:
        for i in range(50):
            self.assertEqual(self.log_in("wrong", ip=f"10.1.0.{i // 10}").status_code, 403)

        self.assert_too_many(self.log_in("right", ip="10.1.1.1"))
        self.assertEqual(self.log_in("wrong", username=" ADMIN@x.com ").status_code, 429)

    def test_successes_do_not_count(self) -> None:
        for _ in range(12):
            self.assertEqual(self.log_in("right").status_code, 200)

    def test_failures_arriving_while_others_check_cannot_overshoot_the_limit(self) -> None:
        from django.contrib.auth import authenticate

        pending, checked, responses = 14, 0, []

        def check_while_others_arrive(*args: Any, **kwargs: Any) -> Any:
            nonlocal pending, checked
            checked += 1
            while pending:
                pending -= 1
                responses.append(self.log_in("wrong"))
            return authenticate(*args, **kwargs)

        with mock.patch("server.api.authenticate", check_while_others_arrive):
            responses.append(self.log_in("wrong"))

        self.assertEqual(checked, 10)
        self.assertEqual(sorted(r.status_code for r in responses), [403] * 10 + [429] * 5)

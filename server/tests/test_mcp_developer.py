import datetime
import json
from typing import Any

from django.test import override_settings
from django.utils import timezone

from server.announcements.models import Announcement
from server.committee.models import Committee, Role
from server.core.models import Guardianship, Player, Team, User
from server.mcp.tools.developer import CHECKS
from server.season.models import Season
from server.subscription.models import Subscription
from server.task.models import Task
from server.tests.base import create_event, make_account
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.ticket.models import Ticket
from server.tournament.models import Match, Tournament
from server.transaction.models import RazorpayTransaction
from server.utils import today


class DeveloperTestCase(McpProtocolTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user.is_superuser = True
        self.user.save()

    def data(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.call(name, arguments)
        self.assertFalse(result["isError"], result)
        return result["structuredContent"]


class TestGate(DeveloperTestCase):
    def test_only_superusers_see_them(self) -> None:
        names = self.names(self.modern("tools/list"))
        self.assertIn("get_system_status", names)
        self.assertIn("explain_access", names)

        self.user.is_superuser = False
        self.user.is_staff = True
        self.user.save()

        names = self.names(self.modern("tools/list"))
        self.assertNotIn("get_system_status", names)
        self.assertNotIn("explain_access", names)

    def test_they_only_read(self) -> None:
        listed = {t["name"]: t for t in self.modern("tools/list").json()["result"]["tools"]}

        for name in ("get_system_status", "explain_access"):
            self.assertTrue(listed[name]["annotations"]["readOnlyHint"], name)


@override_settings(
    GROQ_API_KEY="groq-secret-value",
    SECRET_KEY="django-secret-value",  # noqa: S106
    MCP_ENABLED=True,
)
class TestSystemStatus(DeveloperTestCase):
    def test_it_reports_the_environment_and_never_a_secret(self) -> None:
        with self.settings(OPENCODE_GO_API_KEY="opencode-secret-value"):
            text = json.dumps(self.data("get_system_status", {}))

        for secret in ("groq-secret-value", "django-secret-value", "opencode-secret-value"):
            self.assertNotIn(secret, text)
        status = self.data("get_system_status", {})
        self.assertEqual({"fly", "migrations", "tasks", "cache", "flags", "cron"}, set(status))
        self.assertEqual([], status["migrations"]["unapplied"])
        self.assertIs(True, status["flags"]["groq_api_key_set"])
        self.assertIs(True, status["flags"]["mcp_enabled"])
        self.assertEqual(
            {"FLY_APP_NAME", "FLY_REGION", "FLY_IMAGE_REF", "FLY_MACHINE_VERSION"},
            set(status["fly"]),
        )

    def test_failed_tasks_show_the_error_but_never_the_data(self) -> None:
        Task.objects.create(
            type="SEND_EMAIL",
            data={"to": "victim@example.com"},
            started_at=timezone.now(),
            failed_at=timezone.now(),
            error="x" * 500,
        )
        Task.objects.create(type="SEND_EMAIL")

        status = self.data("get_system_status", {})

        self.assertEqual(1, status["tasks"]["stats"]["failed"])
        self.assertEqual(1, status["tasks"]["stats"]["pending"])
        failure = status["tasks"]["recent_failures"][0]
        self.assertEqual({"task_id", "type", "error", "failed_at"}, set(failure))
        self.assertEqual(200, len(failure["error"]))
        self.assertNotIn("victim@example.com", json.dumps(status))

    def test_a_task_error_is_one_masked_line(self) -> None:
        Task.objects.create(
            type="SEND_EMAIL",
            started_at=timezone.now(),
            failed_at=timezone.now(),
            error="Could not email asha@example.com or call +91 98765 43210\nTraceback: /app/x.py",
        )

        error = self.data("get_system_status", {})["tasks"]["recent_failures"][0]["error"]

        self.assertEqual("Could not email [email] or call [phone]", error)

    def test_the_cache_backend_is_named(self) -> None:
        cache = self.data("get_system_status", {})["cache"]

        self.assertIn("backend", cache)
        self.assertIn("reachable", cache)

    def test_cron_proxies(self) -> None:
        player = Player.objects.create(user=self.user, date_of_birth="2000-01-01")
        Subscription.objects.create(
            player=player,
            season=Season.objects.get(name="Season 2026-2027"),
            is_active=True,
            start_date=today() - datetime.timedelta(days=400),
            end_date=today() - datetime.timedelta(days=1),
        )
        for order, status, age in (
            ("o1", "created", 3),
            ("o2", "completed", 3),
            ("o3", "created", 0),
        ):
            RazorpayTransaction.objects.create(
                order_id=order,
                payment_id="p",
                payment_signature="signature-secret",
                amount=100,
                currency="INR",
                status=status,
                user=self.user,
            )
            RazorpayTransaction.objects.filter(order_id=order).update(
                payment_date=timezone.now() - datetime.timedelta(days=age)
            )

        cron = self.data("get_system_status", {})["cron"]

        self.assertEqual(1, cron["expired_active_subscriptions"])
        self.assertEqual(1, cron["unsettled_orders_over_a_day_old"])
        self.assertNotIn("signature-secret", json.dumps(cron))


class TestExplainAccess(DeveloperTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.subject = User.objects.create(username="s@x.com", email="s@x.com", first_name="Sam")
        self.player = Player.objects.create(user=self.subject, date_of_birth="2000-01-01")
        self.event = create_event("Cup")
        self.tournament = Tournament.objects.create(event=self.event)

    def explain(self, check: str, **args: Any) -> dict[str, Any]:
        arguments = {"check": check, "user_id": self.subject.pk, **args}
        result: dict[str, Any] = self.data("explain_access", arguments)
        return result

    def test_every_check_is_covered(self) -> None:
        self.assertEqual(
            {
                "see_player",
                "answer_invitation_for",
                "manage_tournament",
                "submit_scores",
                "handle_ticket",
                "post_announcements",
                "view_payment_account",
                "team_admin",
                "can_play",
            },
            set(CHECKS),
        )

    def test_the_answer_has_allowed_rule_and_because(self) -> None:
        got = self.explain("see_player", object_ref=str(self.player.pk))

        self.assertEqual({"check", "user_id", "allowed", "rule", "because"}, set(got))
        self.assertTrue(got["allowed"])

    def test_it_never_echoes_an_email(self) -> None:
        got = self.data("explain_access", {"check": "team_admin", "email": "s@x.com"})

        self.assertNotIn("s@x.com", json.dumps(got))
        self.assertEqual(self.subject.pk, got["user_id"])

    def test_without_a_subject_it_explains_the_caller(self) -> None:
        got = self.data("explain_access", {"check": "team_admin"})

        self.assertEqual(self.user.pk, got["user_id"])

    def test_an_unknown_user_is_an_error(self) -> None:
        result = self.call("explain_access", {"check": "team_admin", "user_id": 99999})

        self.assertTrue(result["isError"])

    def test_see_player(self) -> None:
        other = Player.objects.create(
            user=User.objects.create(username="o@x.com"), date_of_birth="2000-01-01"
        )
        self.assertTrue(self.explain("see_player", object_ref=str(self.player.pk))["allowed"])
        self.assertFalse(self.explain("see_player", object_ref=str(other.pk))["allowed"])
        Guardianship.objects.create(user=self.subject, player=other, relation="MO")
        self.assertTrue(self.explain("see_player", object_ref=str(other.pk))["allowed"])

    def test_answer_invitation_for(self) -> None:
        other = Player.objects.create(
            user=User.objects.create(username="o@x.com"), date_of_birth="2000-01-01"
        )
        self.assertFalse(self.explain("answer_invitation_for", object_ref=str(other.pk))["allowed"])
        self.assertTrue(
            self.explain("answer_invitation_for", object_ref=str(self.player.pk))["allowed"]
        )

    def test_manage_tournament(self) -> None:
        ref = {"object_ref": self.event.slug}
        self.assertFalse(self.explain("manage_tournament", **ref)["allowed"])
        self.tournament.directors.add(self.subject)
        self.assertTrue(self.explain("manage_tournament", **ref)["allowed"])

    def test_submit_scores(self) -> None:
        team_a = Team.objects.create(name="A", slug="a")
        team_b = Team.objects.create(name="B", slug="b")
        match = Match.objects.create(
            tournament=self.tournament,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            team_1=team_a,
            team_2=team_b,
            status=Match.Status.SCHEDULED,
        )
        got = self.explain("submit_scores", object_ref=str(match.pk))
        self.assertFalse(got["allowed"])

    def test_handle_ticket(self) -> None:
        ticket = Ticket.objects.create(
            title="T", description="D", created_by=self.user, category_id="Tech"
        )
        self.assertFalse(self.explain("handle_ticket", object_ref=str(ticket.pk))["allowed"])
        self.subject.is_staff = True
        self.subject.save()
        self.assertTrue(self.explain("handle_ticket", object_ref=str(ticket.pk))["allowed"])

    def test_post_announcements(self) -> None:
        self.assertFalse(self.explain("post_announcements")["allowed"])
        committee = Committee.objects.create(
            name="Press", slug="press", can_post_announcements=True
        )
        Role.objects.create(
            user=self.subject,
            committee=committee,
            title="Member",
            start_date=today() - datetime.timedelta(days=1),
        )
        self.assertTrue(self.explain("post_announcements")["allowed"])
        post = Announcement.objects.create(title="P", content="<p>x</p>", author=self.user)
        self.assertFalse(self.explain("post_announcements", object_ref=post.slug)["allowed"])

    def test_view_payment_account(self) -> None:
        account = make_account("kar")
        self.assertFalse(self.explain("view_payment_account", object_ref="kar")["allowed"])
        account.viewers.add(self.subject)
        self.assertTrue(self.explain("view_payment_account", object_ref="kar")["allowed"])

    def test_team_admin(self) -> None:
        team = Team.objects.create(name="Ants", slug="ants")
        self.assertFalse(self.explain("team_admin", object_ref="ants")["allowed"])
        team.admins.add(self.subject)
        self.assertTrue(self.explain("team_admin", object_ref="ants")["allowed"])
        self.assertTrue(self.explain("team_admin")["allowed"])

    def test_can_play(self) -> None:
        got = self.explain("can_play", object_ref=self.event.slug)

        self.assertIn("allowed", got)
        self.assertTrue(got["because"])

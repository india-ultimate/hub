import datetime
from typing import Any

from server.core.models import Guardianship, Player, Team, User
from server.season.models import Season
from server.series.models import SeriesRosterInvitation
from server.subscription.models import Subscription, SubscriptionPlan
from server.tests.test_eligibility import make_series
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.tests.test_subscription_model import make_player
from server.utils import today


class McpToolCase(McpProtocolTestCase):
    bearer = "wtok"

    def setUp(self) -> None:
        super().setUp()
        make_token(self.user, "wtok", scope="hub:read hub:write")

    def data(self, name: str, arguments: dict[str, Any], bearer: str = "wtok") -> Any:
        result = self.call(name, arguments, bearer)
        self.assertFalse(result["isError"], result)
        return result["structuredContent"]

    def failure(self, name: str, arguments: dict[str, Any], bearer: str = "wtok") -> str:
        result = self.call(name, arguments, bearer)
        self.assertTrue(result["isError"], result)
        return str(result["structuredContent"]["message"])

    def ask(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        asked = self.data(name, arguments)
        self.assertFalse(asked["done"])
        return dict(asked)

    def confirmed(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self.ask(name, arguments)["confirmation"]
        return self.call(name, {**arguments, "confirmation": state})


class InvitationCase(McpToolCase):
    def setUp(self) -> None:
        super().setUp()
        season = Season.objects.get(name="Season 2026-2027")
        self.series = make_series(season)
        self.team = Team.objects.create(name="Team A")
        self.series.teams.add(self.team)
        self.admin = User.objects.create(
            username="admin@example.com", email="admin@example.com", first_name="Tej"
        )
        self.team.admins.add(self.admin)
        self.me = Player.objects.create(user=self.user, date_of_birth="2000-01-01")
        self.subscribe(self.me)
        self.invitation = self.invite(self.me)

    def subscribe(self, player: Player) -> None:
        season = Season.objects.get(name="Season 2026-2027")
        Subscription.objects.create(
            player=player,
            season=season,
            plan=SubscriptionPlan.objects.get(season=season, type__slug="regular"),
            is_active=True,
            waiver_valid=True,
            coc_agreed=True,
            start_date=season.start_date,
            end_date=season.end_date,
        )

    def invite(self, player: Player, **kw: Any) -> SeriesRosterInvitation:
        return SeriesRosterInvitation.objects.create(
            series=self.series, team=self.team, from_user=self.admin, to_player=player, **kw
        )

    def ward(self) -> Player:
        ward = make_player("ward@example.com")
        self.subscribe(ward)
        Guardianship.objects.create(user=self.user, player=ward, relation="MO")
        return ward


class TestListSeriesInvitations(InvitationCase):
    def test_lists_pending_ones_for_me_and_my_wards(self) -> None:
        ward = self.ward()
        for_ward = self.invite(ward)
        self.invite(make_player("other@example.com"))
        declined = self.invite(self.me)
        declined.status = SeriesRosterInvitation.Status.DECLINED
        declined.save()

        rows = self.data("list_series_invitations", {})["invitations"]

        self.assertEqual({self.invitation.id, for_ward.id}, {r["invitation_id"] for r in rows})
        mine = next(r for r in rows if r["invitation_id"] == self.invitation.id)
        self.assertEqual(self.series.slug, mine["series_slug"])
        self.assertEqual(self.team.slug, mine["team_slug"])
        self.assertEqual(self.me.id, mine["player"]["player_id"])
        self.assertTrue(mine["player"]["is_you"])
        self.assertEqual(str(self.invitation.expires_on), mine["expires_on"])
        self.assertFalse(mine["expired"])
        theirs = next(r for r in rows if r["invitation_id"] == for_ward.id)
        self.assertFalse(theirs["player"]["is_you"])
        self.assertNotIn("ward@example.com", str(rows))

    def test_marks_an_invitation_past_its_date_as_expired(self) -> None:
        self.invitation.expires_on = today() - datetime.timedelta(days=1)
        self.invitation.save()

        rows = self.data("list_series_invitations", {})["invitations"]

        self.assertTrue(rows[0]["expired"])


class TestAnswerSeriesInvitation(InvitationCase):
    def answer(self, invitation: SeriesRosterInvitation, answer: str) -> dict[str, Any]:
        return self.confirmed(
            "answer_series_invitation", {"invitation_id": invitation.id, "answer": answer}
        )

    def test_asks_first_and_names_the_team(self) -> None:
        asked = self.ask(
            "answer_series_invitation", {"invitation_id": self.invitation.id, "answer": "accept"}
        )

        self.assertIn("Team A", asked["needs_confirmation"])
        self.invitation.refresh_from_db()
        self.assertEqual(SeriesRosterInvitation.Status.PENDING, self.invitation.status)

    def test_accepting_joins_the_roster(self) -> None:
        result = self.answer(self.invitation, "accept")

        self.assertFalse(result["isError"], result)
        self.assertEqual("accept", result["structuredContent"]["answer"])
        self.invitation.refresh_from_db()
        self.assertEqual(SeriesRosterInvitation.Status.ACCEPTED, self.invitation.status)
        self.assertTrue(self.series.seriesregistration_set.filter(player=self.me).exists())

    def test_declining(self) -> None:
        result = self.answer(self.invitation, "decline")

        self.assertEqual("decline", result["structuredContent"]["answer"])
        self.invitation.refresh_from_db()
        self.assertEqual(SeriesRosterInvitation.Status.DECLINED, self.invitation.status)

    def test_a_guardian_answers_for_a_ward(self) -> None:
        ward = self.ward()
        invitation = self.invite(ward)

        asked = self.ask(
            "answer_series_invitation", {"invitation_id": invitation.id, "answer": "accept"}
        )
        result = self.answer(invitation, "accept")

        self.assertIn(ward.user.get_full_name(), asked["needs_confirmation"])
        self.assertFalse(result["isError"], result)
        invitation.refresh_from_db()
        self.assertEqual(SeriesRosterInvitation.Status.ACCEPTED, invitation.status)

    def test_an_expired_invitation_is_refused(self) -> None:
        self.invitation.expires_on = today() - datetime.timedelta(days=1)
        self.invitation.save()

        for answer in ("accept", "decline"):
            with self.subTest(answer=answer):
                result = self.answer(self.invitation, answer)

                self.assertTrue(result["isError"])
                self.assertEqual(
                    "This invitation has expired. Ask the team admin to invite you again.",
                    result["structuredContent"]["message"],
                )
        self.invitation.refresh_from_db()
        self.assertEqual(SeriesRosterInvitation.Status.PENDING, self.invitation.status)

    def test_someone_elses_invitation_is_denied_and_not_described(self) -> None:
        other = self.invite(make_player("other@example.com"))

        message = self.failure(
            "answer_series_invitation", {"invitation_id": other.id, "answer": "accept"}
        )

        self.assertEqual(f"No pending invitation {other.id} for you or your wards", message)
        self.assertNotIn("other@example.com", message)
        other.refresh_from_db()
        self.assertEqual(SeriesRosterInvitation.Status.PENDING, other.status)

    def test_an_answered_invitation_is_not_pending_any_more(self) -> None:
        self.answer(self.invitation, "decline")

        message = self.failure(
            "answer_series_invitation", {"invitation_id": self.invitation.id, "answer": "accept"}
        )

        self.assertIn("No pending invitation", message)

    def test_a_missing_invitation_says_so(self) -> None:
        message = self.failure(
            "answer_series_invitation", {"invitation_id": 99999, "answer": "accept"}
        )

        self.assertEqual("No pending invitation 99999 for you or your wards", message)

from typing import Any

from django.core import mail
from django.test import override_settings

from server.core.models import Player, Team, UCPerson, User
from server.season.models import Season
from server.series.models import Role, SeriesRegistration, SeriesRosterInvitation
from server.subscription.models import Subscription, SubscriptionPlan
from server.tests.test_eligibility import make_series
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.tests.test_mcp_tools_tournaments import TournamentToolsTestCase
from server.tests.test_subscription_model import make_player
from server.tournament.models import Match, MatchScore, UCRegistration


class ConfirmedCalls(McpProtocolTestCase):
    bearer = "wtok"

    def confirmed(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        asked = self.call(name, arguments)["structuredContent"]
        self.assertIn("confirmation", asked)
        return self.call(name, {**arguments, "confirmation": asked["confirmation"]})


class SeriesToolsTestCase(ConfirmedCalls):
    def setUp(self) -> None:
        super().setUp()
        make_token(self.user, "wtok", scope="hub:read hub:write")
        self.season = Season.objects.get(name="Season 2026-2027")
        self.series = make_series(self.season)
        self.team = Team.objects.create(name="Team A")
        self.team.admins.add(self.user)
        self.series.teams.add(self.team)
        self.args = {"series_slug": self.series.slug, "team_slug": self.team.slug}

    def demote(self) -> None:
        self.team.admins.clear()
        Team.objects.create(name="Elsewhere").admins.add(self.user)

    def subscribed(self, email: str) -> Player:
        player = make_player(email)
        player.user.first_name = "Quinn"
        player.user.save()
        return self.subscribe(player)

    def subscribe(self, player: Player) -> Player:
        Subscription.objects.create(
            player=player,
            season=self.season,
            plan=SubscriptionPlan.objects.get(season=self.season, type__slug="regular"),
            is_active=True,
            waiver_valid=True,
            coc_agreed=True,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        return player

    def rostered(self, email: str, role: str = Role.DEFAULT) -> SeriesRegistration:
        player = self.subscribed(email)
        return SeriesRegistration.objects.create(
            series=self.series, team=self.team, player=player, role=role
        )


class TestSeriesRoster(SeriesToolsTestCase):
    def test_the_roster_schema_carries_the_registration_id(self) -> None:
        registration = self.rostered("p@x.com")
        self.client.force_login(self.user)

        rows = self.client.get(
            f"/api/series/{self.series.slug}/team/{self.team.slug}/roster"
        ).json()

        self.assertEqual(registration.pk, rows[0]["id"])

    def test_admin_sees_roster_and_flagged_pending_invitations(self) -> None:
        registration = self.rostered("p@x.com", Role.CAPTAIN)
        invitee = make_player("q@x.com")
        old = SeriesRosterInvitation.objects.create(
            series=self.series, from_user=self.user, to_player=invitee, team=self.team
        )
        SeriesRosterInvitation.objects.filter(pk=old.pk).update(expires_on="2020-01-01")

        data = self.call("get_series_roster", self.args)["structuredContent"]

        self.assertEqual([registration.pk], [m["registration_id"] for m in data["members"]])
        self.assertEqual("CAP", data["members"][0]["role"])
        (pending,) = data["pending_invitations"]
        self.assertEqual(old.pk, pending["invitation_id"])
        self.assertEqual(invitee.pk, pending["player_id"])
        self.assertTrue(pending["expired"])
        self.assertNotIn("x.com", str(data))

    def test_a_non_admin_sees_no_invitations(self) -> None:
        self.demote()

        data = self.call("get_series_roster", self.args)["structuredContent"]

        self.assertEqual([], data["pending_invitations"])

    def test_unknown_team_is_a_message(self) -> None:
        result = self.call("get_series_roster", {**self.args, "team_slug": "nope"})

        self.assertTrue(result["isError"])


class TestSeriesRosterWrites(SeriesToolsTestCase):
    @override_settings(EMAIL_SECRET_KEY="test-secret")  # noqa: S106
    def test_invite_asks_first_then_emails(self) -> None:
        invitee = self.subscribed("q@x.com")
        args = {**self.args, "invites": [{"player_id": invitee.pk, "role": "COACH"}]}

        asked = self.call("invite_to_series_roster", args)["structuredContent"]

        self.assertIn("Email", asked["needs_confirmation"])
        self.assertIn("Quinn", asked["needs_confirmation"])
        self.assertEqual(0, SeriesRosterInvitation.objects.count())

        done = self.confirmed("invite_to_series_roster", args)

        self.assertFalse(done["isError"], done)
        self.assertEqual(1, SeriesRosterInvitation.objects.count())
        self.assertEqual(1, len(mail.outbox))
        self.assertEqual("invited", done["structuredContent"]["results"][0]["outcome"])

    def test_invite_by_a_non_admin_is_refused_in_words(self) -> None:
        self.demote()
        invitee = make_player("q@x.com")
        args = {**self.args, "invites": [{"player_id": invitee.pk}]}

        done = self.confirmed("invite_to_series_roster", args)

        self.assertTrue(done["isError"])
        self.assertIn("Not allowed", done["structuredContent"]["message"])
        self.assertEqual(0, SeriesRosterInvitation.objects.count())

    def test_revoke(self) -> None:
        invitation = SeriesRosterInvitation.objects.create(
            series=self.series,
            from_user=self.user,
            to_player=make_player("q@x.com"),
            team=self.team,
        )

        done = self.confirmed("revoke_series_invitations", {"invitation_ids": [invitation.pk]})

        self.assertFalse(done["isError"], done)
        invitation.refresh_from_db()
        self.assertEqual("Revoked", invitation.status)

    def test_another_teams_invitation_is_refused_without_naming_anyone(self) -> None:
        other = Team.objects.create(name="Other Team", slug="other-team")
        player = make_player("secret@x.com")
        User.objects.filter(pk=player.user_id).update(first_name="Secretname")
        invitation = SeriesRosterInvitation.objects.create(
            series=self.series, from_user=self.user, to_player=player, team=other
        )

        result = self.call("revoke_series_invitations", {"invitation_ids": [invitation.pk]})

        self.assertTrue(result["isError"])
        self.assertNotIn("Secretname", str(result))
        invitation.refresh_from_db()
        self.assertNotEqual("Revoked", invitation.status)

    def test_set_roles_resolves_the_registration(self) -> None:
        registration = self.rostered("p@x.com")
        args = {**self.args, "changes": [{"player_id": registration.player_id, "role": "CAP"}]}

        done = self.confirmed("set_series_roles", args)

        self.assertFalse(done["isError"], done)
        registration.refresh_from_db()
        self.assertEqual("CAP", registration.role)

    def test_set_roles_for_someone_not_on_the_roster(self) -> None:
        args = {**self.args, "changes": [{"player_id": 999999, "role": "CAP"}]}

        asked = self.call("set_series_roles", args)

        self.assertTrue(asked["isError"])
        self.assertIn("not on the series roster", asked["structuredContent"]["message"])

    def test_add_myself(self) -> None:
        self.subscribe(Player.objects.create(user=self.user, date_of_birth="2000-01-01"))

        done = self.confirmed("add_myself_to_series_roster", self.args)

        self.assertFalse(done["isError"], done)
        self.assertTrue(SeriesRegistration.objects.filter(team=self.team).exists())


class TestUpdateTeam(SeriesToolsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mate = User.objects.create(username="m@x.com", email="m@x.com")
        self.mate_player = Player.objects.create(user=self.mate, date_of_birth="2000-01-01")

    def test_details_change(self) -> None:
        args = {"team_slug": self.team.slug, "city": "Pune", "state_ut": "MH"}

        done = self.confirmed("update_team", args)

        self.assertFalse(done["isError"], done)
        self.team.refresh_from_db()
        self.assertEqual("Pune", self.team.city)

    def test_rename_warns_that_the_link_changes_and_returns_the_new_slug(self) -> None:
        args = {"team_slug": self.team.slug, "name": "Renamed Team"}

        asked = self.call("update_team", args)["structuredContent"]
        self.assertIn("link", asked["needs_confirmation"])
        done = self.confirmed("update_team", args)

        self.assertFalse(done["isError"], done)
        self.assertEqual("renamed-team", done["structuredContent"]["team_slug"])

    def test_admins_are_added_and_removed_by_player(self) -> None:
        self.confirmed(
            "update_team",
            {"team_slug": self.team.slug, "add_admin_player_ids": [self.mate_player.pk]},
        )
        self.assertEqual({self.user, self.mate}, set(self.team.admins.all()))

        self.confirmed(
            "update_team",
            {"team_slug": self.team.slug, "remove_admin_player_ids": [self.mate_player.pk]},
        )
        self.assertEqual({self.user}, set(self.team.admins.all()))

    def test_three_letter_states_are_allowed_and_bad_ones_refused(self) -> None:
        done = self.confirmed("update_team", {"team_slug": self.team.slug, "state_ut": "CDG"})
        self.assertFalse(done["isError"], done)
        self.team.refresh_from_db()
        self.assertEqual("CDG", self.team.state_ut)

        bad = self.call("update_team", {"team_slug": self.team.slug, "state_ut": "ZZ"})
        self.assertTrue(bad["isError"])

    def test_a_blank_name_is_refused(self) -> None:
        result = self.call("update_team", {"team_slug": self.team.slug, "name": "  "})

        self.assertIn("blank", result["structuredContent"]["message"])

    def test_removing_yourself_is_refused(self) -> None:
        mine = Player.objects.create(user=self.user, date_of_birth="2000-01-01")
        self.team.admins.add(self.mate)

        result = self.call(
            "update_team", {"team_slug": self.team.slug, "remove_admin_player_ids": [mine.pk]}
        )

        self.assertTrue(result["isError"])
        self.assertEqual(2, self.team.admins.count())

    def test_a_non_admin_is_refused(self) -> None:
        self.demote()

        result = self.call("update_team", {"team_slug": self.team.slug, "city": "Pune"})

        self.assertTrue(result["isError"])
        self.assertIn("Not allowed", result["structuredContent"]["message"])

    def test_descriptions_point_at_the_upload_link(self) -> None:
        tools = {t["name"]: t for t in self.modern("tools/list").json()["result"]["tools"]}

        self.assertIn("create_upload_link", tools["update_team"]["description"])


class ResultsTestCase(ConfirmedCalls, TournamentToolsTestCase):
    def setUp(self) -> None:
        super().setUp()
        make_token(self.user, "wtok", scope="hub:read hub:write")
        self.player = Player.objects.create(
            user=self.user, date_of_birth="2000-01-01", ultimate_central_id=777
        )
        person = UCPerson.objects.create(id=777, email="cap@x.com", slug="cap", first_name="Cap")
        self.match = self.second
        self.match.refresh_from_db()
        mine, theirs = self.match.team_1, self.match.team_2
        if mine is None or theirs is None:
            self.fail("the match has no teams")
        self.mine, self.theirs = mine, theirs
        UCRegistration.objects.create(
            event=self.event, team=self.mine, person=person, roles=["captain", "player"]
        )


class TestMatchScore(ResultsTestCase):
    def test_list_match_rosters(self) -> None:
        data = self.call("list_match_rosters", {"match_id": self.match.pk})["structuredContent"]

        self.assertEqual({"match_id", "id_kind", "team_1", "team_2"}, set(data))
        self.assertEqual("uc_person_id", data["id_kind"])
        self.assertIn("uc_person_id", data["team_1"]["players"][0])
        self.assertNotIn("cap@x.com", str(data))

    def test_preview_names_teams_in_match_order_and_warns(self) -> None:
        args = {"match_id": self.match.pk, "team_1_score": 15, "team_2_score": 12}

        asked = self.call("submit_match_score", args)["structuredContent"]["needs_confirmation"]

        self.assertLess(asked.index(self.mine.name), asked.index(self.theirs.name))
        self.assertIn("final", asked)

    def test_one_side_is_waiting_then_the_other_makes_it_final(self) -> None:
        args = {"match_id": self.match.pk, "team_1_score": 15, "team_2_score": 12}

        done = self.confirmed("submit_match_score", args)["structuredContent"]

        self.assertEqual("waiting", done["outcome"])
        self.match.refresh_from_db()
        self.assertNotEqual(Match.Status.COMPLETED, self.match.status)

        other = User.objects.create(username="o@x.com", email="o@x.com")
        Player.objects.create(user=other, date_of_birth="2000-01-01", ultimate_central_id=778)
        UCRegistration.objects.create(
            event=self.event,
            team=self.theirs,
            person=UCPerson.objects.create(id=778, email="o@x.com", slug="o", first_name="O"),
            roles=["captain"],
        )
        make_token(other, "otok", scope="hub:read hub:write")
        body = {"name": "submit_match_score", "arguments": args}
        asked = self.modern("tools/call", body, bearer="otok").json()["result"]
        body["arguments"] = {**args, "confirmation": asked["structuredContent"]["confirmation"]}
        final = self.modern("tools/call", body, bearer="otok").json()["result"]

        self.assertEqual("final", final["structuredContent"]["outcome"])

    def test_a_disagreement_is_reported(self) -> None:
        self.match.suggested_score_team_2 = MatchScore.objects.create(
            score_team_1=1, score_team_2=1, entered_by=self.player
        )
        self.match.save()
        args = {"match_id": self.match.pk, "team_1_score": 15, "team_2_score": 12}

        done = self.confirmed("submit_match_score", args)["structuredContent"]

        self.assertEqual("disagree", done["outcome"])

    def test_a_team_admin_without_a_roster_role_gets_a_clear_message(self) -> None:
        UCRegistration.objects.filter(team=self.mine).delete()
        self.mine.admins.add(self.user)
        args = {"match_id": self.match.pk, "team_1_score": 15, "team_2_score": 12}

        result = self.call("submit_match_score", args)

        self.assertTrue(result["isError"])
        self.assertIn("roster", result["structuredContent"]["message"])

    def test_unknown_match(self) -> None:
        result = self.call(
            "submit_match_score", {"match_id": 999999, "team_1_score": 1, "team_2_score": 0}
        )

        self.assertTrue(result["isError"])


class TestSpiritScore(ResultsTestCase):
    def block(self, **extra: Any) -> dict[str, Any]:
        return {"rules": 2, "fouls": 2, "fair": 2, "positive": 2, "communication": 2, **extra}

    def args(self, **extra: Any) -> dict[str, Any]:
        return {
            "match_id": self.match.pk,
            "team_id": self.mine.pk,
            "opponent": self.block(**extra),
            "self": self.block(),
        }

    def submit_score(self) -> None:
        self.confirmed(
            "submit_match_score",
            {"match_id": self.match.pk, "team_1_score": 15, "team_2_score": 12},
        )

    def test_the_preview_names_mvp_and_warns_about_overwrite(self) -> None:
        self.submit_score()
        nominee = UCRegistration.objects.filter(team=self.theirs)[0]

        asked = self.call("submit_spirit_score", self.args(mvp_uc_person_id=nominee.person_id))[
            "structuredContent"
        ]["needs_confirmation"]

        self.assertIn(nominee.person.first_name, asked)
        self.assertIn("replaces", asked)

    def test_saves_once_the_score_is_in(self) -> None:
        self.submit_score()

        done = self.confirmed("submit_spirit_score", self.args(comments="Great game"))

        self.assertFalse(done["isError"], done)
        self.match.refresh_from_db()
        self.assertIsNotNone(self.match.spirit_score_team_2)

    def test_before_the_score_hubs_message_comes_through(self) -> None:
        done = self.confirmed("submit_spirit_score", self.args())

        self.assertTrue(done["isError"])
        self.assertIn("Submit the match score", done["structuredContent"]["message"])

    def test_out_of_range_is_caught_before_asking(self) -> None:
        result = self.call("submit_spirit_score", self.args(rules=5))

        self.assertTrue(result["isError"])
        self.assertIn("rules", result["structuredContent"]["message"])

    def test_a_non_captain_is_refused(self) -> None:
        UCRegistration.objects.filter(team=self.mine).delete()
        self.mine.admins.add(self.user)

        result = self.call("submit_spirit_score", self.args())

        self.assertTrue(result["isError"])

import datetime
from typing import Any

from django.test import override_settings

from server.core.models import Player, Team, User
from server.mcp.registry import TOOLS, validate
from server.mcp.tools import director
from server.series.models import Series
from server.tests.base import create_event
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.tournament.models import (
    Match,
    MatchScore,
    Registration,
    Tournament,
    TournamentField,
)
from server.tournament_agent.models import AgentProposal, TournamentAgentSession
from server.tournament_agent.tools import HANDLERS, READ_ONLY_TOOLS


class DirectorTestCase(McpProtocolTestCase):
    bearer = "wtok"

    def setUp(self) -> None:
        super().setUp()
        make_token(self.user, "wtok", scope="hub:read hub:write")
        self.event = create_event("Nationals 2026")
        self.tournament = Tournament.objects.create(event=self.event)
        self.tournament.directors.add(self.user)
        self.slug = self.event.slug
        self.other_event = create_event("Other Cup")
        self.other = Tournament.objects.create(event=self.other_event)

    def data(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.call(name, arguments)
        self.assertFalse(result["isError"], result)
        return result["structuredContent"]

    def confirmed(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        first = self.call(name, arguments)["structuredContent"]
        self.assertFalse(first["done"])
        return self.call(name, {**arguments, "confirmation": first["confirmation"]})

    def propose(self, **arguments: Any) -> dict[str, Any]:
        args = {"event_slug": self.slug, "tool": "propose_create_field", "arguments": arguments}
        result: dict[str, Any] = self.data("propose_tournament_change", args)
        return result


class TestDescriptors(DirectorTestCase):
    def test_enums_come_from_the_agent_and_leave_out_the_dangerous_ones(self) -> None:
        self.assertEqual(sorted(READ_ONLY_TOOLS), director.READ_TOOLS)
        self.assertNotIn("ask_user", director.READ_TOOLS + director.PROPOSE_TOOLS)
        for banned in ("propose_start_tournament", "propose_delete_stage", "propose_full_setup"):
            self.assertIn(banned, HANDLERS)
            self.assertNotIn(banned, director.PROPOSE_TOOLS)
        self.assertIn("propose_match_score", director.PROPOSE_TOOLS)

    def test_list_director_tools_gives_schemas(self) -> None:
        tools = {t["tool"]: t for t in self.data("list_director_tools", {})["tools"]}

        self.assertEqual(set(director.READ_TOOLS + director.PROPOSE_TOOLS), set(tools))
        score = tools["propose_match_score"]
        self.assertEqual("proposal", score["kind"])
        self.assertIn("match_id", score["parameters"]["properties"])
        self.assertEqual("read", tools["list_fields"]["kind"])

    def test_every_tool_comes_with_an_example_that_fits_its_parameters(self) -> None:
        tools = self.data("list_director_tools", {})["tools"]

        for row in tools:
            with self.subTest(tool=row["tool"]):
                self.assertIsInstance(row["example"], dict)
                self.assertIsNone(validate(row["example"], row["parameters"]))
        score = next(t for t in tools if t["tool"] == "propose_match_score")
        self.assertEqual(set(score["parameters"].get("required", [])), set(score["example"]))

    def test_proposing_points_to_the_tool_list(self) -> None:
        description = TOOLS["propose_tournament_change"].description

        self.assertIn("list_director_tools", description)
        self.assertIn("argument", description)

    def test_only_directors_see_the_tools(self) -> None:
        self.tournament.directors.clear()

        self.assertNotIn("list_director_tools", self.names(self.modern("tools/list")))
        self.assertNotIn("get_tournament_ops_report", self.names(self.modern("tools/list")))

    def test_the_flag_hides_them_too(self) -> None:
        with override_settings(TOURNAMENT_AGENT_ENABLED=False):
            self.assertNotIn("list_director_tools", self.names(self.modern("tools/list")))


class TestReads(DirectorTestCase):
    def test_a_read_runs_the_agents_own_tool(self) -> None:
        TournamentField.objects.create(tournament=self.tournament, name="Field 1")

        data = self.data("read_tournament_ops", {"event_slug": self.slug, "tool": "list_fields"})

        self.assertEqual("Field 1", data["result"]["fields"][0]["name"])
        self.assertEqual("list_fields", data["tool"])

    def test_it_uses_the_users_own_session(self) -> None:
        self.data("read_tournament_ops", {"event_slug": self.slug, "tool": "list_fields"})
        self.data("read_tournament_ops", {"event_slug": self.slug, "tool": "list_fields"})

        self.assertEqual(
            1,
            TournamentAgentSession.objects.filter(
                user=self.user, tournament=self.tournament
            ).count(),
        )

    def test_a_tournament_they_do_not_direct_is_refused(self) -> None:
        result = self.call(
            "read_tournament_ops", {"event_slug": self.other_event.slug, "tool": "list_fields"}
        )

        self.assertTrue(result["isError"])
        self.assertIn("Not allowed", result["structuredContent"]["message"])
        self.assertEqual(0, TournamentAgentSession.objects.count())

    def test_the_flag_off_refuses(self) -> None:
        with override_settings(TOURNAMENT_AGENT_ENABLED=False):
            result = self.call(
                "read_tournament_ops", {"event_slug": self.slug, "tool": "list_fields"}
            )

        self.assertNotIn("structuredContent", result)

    def test_a_proposal_tool_is_not_a_read(self) -> None:
        result = self.call(
            "read_tournament_ops", {"event_slug": self.slug, "tool": "propose_create_field"}
        )

        self.assertTrue(result["isError"])

    def test_arguments_are_checked_against_the_tools_schema(self) -> None:
        result = self.call(
            "read_tournament_ops",
            {"event_slug": self.slug, "tool": "get_match_spirit", "arguments": {"match_id": "x"}},
        )

        self.assertTrue(result["isError"])
        self.assertIn("match_id", result["structuredContent"]["message"])

    def test_the_phase_can_forbid_a_tool(self) -> None:
        result = self.call(
            "propose_tournament_change",
            {
                "event_slug": self.slug,
                "tool": "propose_match_score",
                "arguments": {"match_id": 1, "score_team_1": 15, "score_team_2": 3},
            },
        )

        self.assertTrue(result["isError"])
        self.assertIn("not available right now", result["structuredContent"]["message"])
        self.assertEqual(0, AgentProposal.objects.count())


class TestProposals(DirectorTestCase):
    def test_a_proposal_is_pending_and_listed_until_confirmed(self) -> None:
        proposed = self.propose(name="Field 9")

        self.assertEqual("Create field 'Field 9'", proposed["summary"])
        self.assertFalse(TournamentField.objects.filter(tournament=self.tournament).exists())
        listed = self.data("list_tournament_proposals", {"event_slug": self.slug})["proposals"]
        self.assertEqual([proposed["proposal_id"]], [p["proposal_id"] for p in listed])
        self.assertEqual("propose_create_field", listed[0]["tool"])

    def test_a_second_proposal_of_the_same_kind_replaces_the_first(self) -> None:
        first = self.propose(name="Field 1")["proposal_id"]
        second = self.propose(name="Field 2")["proposal_id"]

        self.assertEqual("expired", AgentProposal.objects.get(pk=first).status)
        listed = self.data("list_tournament_proposals", {"event_slug": self.slug})["proposals"]
        self.assertEqual([second], [p["proposal_id"] for p in listed])

    def test_confirming_applies_once(self) -> None:
        pid = self.propose(name="Field 9")["proposal_id"]

        first = self.confirmed("confirm_tournament_proposal", {"proposal_id": pid})
        second = self.confirmed("confirm_tournament_proposal", {"proposal_id": pid})

        self.assertFalse(first["isError"], first)
        self.assertTrue(second["isError"])
        self.assertEqual(1, TournamentField.objects.filter(tournament=self.tournament).count())

    def test_confirm_asks_first_and_says_what_it_does(self) -> None:
        pid = self.propose(name="Field 9")["proposal_id"]

        asked = self.call("confirm_tournament_proposal", {"proposal_id": pid})["structuredContent"]

        self.assertIn("Create field 'Field 9'", asked["needs_confirmation"])
        self.assertFalse(TournamentField.objects.exists())

    def test_rejecting_closes_it(self) -> None:
        pid = self.propose(name="Field 9")["proposal_id"]

        self.data("reject_tournament_proposal", {"proposal_id": pid})

        self.assertEqual("rejected", AgentProposal.objects.get(pk=pid).status)
        late = self.confirmed("confirm_tournament_proposal", {"proposal_id": pid})
        self.assertTrue(late["isError"])
        self.assertFalse(TournamentField.objects.exists())

    def test_someone_elses_proposal_is_refused(self) -> None:
        stranger = User.objects.create(username="s@x.com", email="s@x.com")
        self.tournament.directors.add(stranger)
        session = TournamentAgentSession.objects.create(
            user=stranger, tournament=self.tournament, model_id="m"
        )
        proposal = AgentProposal.objects.create(
            session=session, tool_name="propose_create_field", summary="x", payload={"name": "F"}
        )

        for name in ("confirm_tournament_proposal", "reject_tournament_proposal"):
            result = self.call(name, {"proposal_id": proposal.pk})
            self.assertTrue(result["isError"], name)
        self.assertEqual("pending", AgentProposal.objects.get(pk=proposal.pk).status)

    def test_a_proposal_for_a_tournament_no_longer_directed_is_refused(self) -> None:
        pid = self.propose(name="Field 9")["proposal_id"]
        self.tournament.directors.clear()
        self.other.directors.add(self.user)

        result = self.call("reject_tournament_proposal", {"proposal_id": pid})

        self.assertTrue(result["isError"])
        self.assertEqual("pending", AgentProposal.objects.get(pk=pid).status)

    def test_list_for_a_tournament_they_do_not_direct_is_refused(self) -> None:
        result = self.call("list_tournament_proposals", {"event_slug": self.other_event.slug})

        self.assertTrue(result["isError"])

    def test_the_flag_off_refuses_confirm(self) -> None:
        pid = self.propose(name="Field 9")["proposal_id"]

        with override_settings(TOURNAMENT_AGENT_ENABLED=False):
            result = self.call("confirm_tournament_proposal", {"proposal_id": pid})

        self.assertNotIn("structuredContent", result)
        self.assertEqual("pending", AgentProposal.objects.get(pk=pid).status)

    def test_the_dangerous_proposals_are_not_offered(self) -> None:
        result = self.call(
            "propose_tournament_change",
            {"event_slug": self.slug, "tool": "propose_start_tournament", "arguments": {}},
        )

        self.assertTrue(result["isError"])


class TestOpsReport(DirectorTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.series = Series.objects.create(
            name="S",
            slug="s",
            start_date=self.event.start_date,
            end_date=self.event.end_date,
            type="MXD",
            category="Club",
            series_roster_max_players=20,
            event_min_players_male=2,
            event_min_players_female=1,
            event_max_players_male=10,
            event_max_players_female=10,
            event_min_players_total=3,
        )
        self.event.series = self.series
        self.event.save()
        self.team_a, self.team_b = (
            Team.objects.create(name="Ants", slug="ants"),
            Team.objects.create(name="Bees", slug="bees"),
        )
        self.tournament.teams.set([self.team_a])
        self.past = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)

    def match(self, **kw: Any) -> Match:
        return Match.objects.create(
            tournament=self.tournament,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            team_1=self.team_a,
            team_2=self.team_b,
            **kw,
        )

    def report(self) -> dict[str, Any]:
        data: dict[str, Any] = self.data("get_tournament_ops_report", {"event_slug": self.slug})
        return data

    def test_matches_past_start_without_scores_and_unscheduled(self) -> None:
        field = TournamentField.objects.create(tournament=self.tournament, name="F1")
        late = self.match(time=self.past, field=field, status=Match.Status.SCHEDULED)
        loose = self.match(status=Match.Status.YET_TO_FIX)
        done = self.match(
            time=self.past + datetime.timedelta(hours=3), field=field, status=Match.Status.COMPLETED
        )

        report = self.report()

        self.assertEqual([late.pk], [m["match_id"] for m in report["unscored_matches"]])
        self.assertEqual([loose.pk], [m["match_id"] for m in report["unscheduled_matches"]])
        self.assertNotIn(done.pk, [m["match_id"] for m in report["unscored_matches"]])

    def test_score_disagreements_and_missing_spirit(self) -> None:
        player = Player.objects.create(user=self.user, date_of_birth="1990-01-01", match_up="M")
        match = self.match(status=Match.Status.SCHEDULED)
        done = self.match(status=Match.Status.COMPLETED)
        match.suggested_score_team_1 = MatchScore.objects.create(
            score_team_1=15, score_team_2=3, entered_by=player
        )
        match.suggested_score_team_2 = MatchScore.objects.create(
            score_team_1=15, score_team_2=5, entered_by=player
        )
        match.save()

        report = self.report()

        self.assertEqual([match.pk], [m["match_id"] for m in report["score_disagreements"]])
        self.assertEqual([done.pk], [m["match_id"] for m in report["missing_spirit"]])

    def test_a_completed_match_is_no_longer_a_disagreement(self) -> None:
        player = Player.objects.create(user=self.user, date_of_birth="1990-01-01", match_up="M")
        match = self.match(status=Match.Status.COMPLETED)
        match.suggested_score_team_1 = MatchScore.objects.create(
            score_team_1=15, score_team_2=3, entered_by=player
        )
        match.suggested_score_team_2 = MatchScore.objects.create(
            score_team_1=15, score_team_2=5, entered_by=player
        )
        match.save()

        self.assertEqual([], self.report()["score_disagreements"])

    def test_unpaid_teams_and_rosters_under_the_minimum(self) -> None:
        for index, team in enumerate((self.team_a, self.team_b)):
            player = Player.objects.create(
                user=User.objects.create(username=f"p{index}@x.com"),
                date_of_birth="1990-01-01",
                match_up="M",
            )
            Registration.objects.create(event=self.event, team=team, player=player)

        report = self.report()

        self.assertEqual([self.team_b.pk], [t["team_id"] for t in report["unpaid_teams"]])
        short = {t["team_id"]: t for t in report["teams_under_minimum"]}
        self.assertEqual({self.team_a.pk, self.team_b.pk}, set(short))
        self.assertEqual({"total": 1, "male": 1, "female": 0}, short[self.team_a.pk]["roster"])
        self.assertEqual({"total": 3, "male": 2, "female": 1}, short[self.team_a.pk]["minimum"])

    def test_a_tournament_they_do_not_direct_is_refused(self) -> None:
        result = self.call("get_tournament_ops_report", {"event_slug": self.other_event.slug})

        self.assertTrue(result["isError"])

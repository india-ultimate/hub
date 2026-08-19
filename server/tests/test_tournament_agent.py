"""Offline unit tests for tournament agent (no OpenCode API required)."""

from __future__ import annotations

import inspect
import json
import re
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

from django.http import StreamingHttpResponse
from django.test import TestCase
from django.utils.dateparse import parse_datetime

from server.core.models import Player, Team, User
from server.tests.base import ApiBaseTestCase, create_event
from server.tournament.models import (
    Match,
    Pool,
    PositionPool,
    Registration,
    SpiritScore,
    SwissRound,
    Tournament,
    TournamentField,
)
from server.tournament.utils import build_bracket, build_pool
from server.tournament.utils import start_tournament as begin_tournament
from server.tournament_agent.catalog import (
    AGENT_MODELS,
    default_model_id,
    get_model,
    is_allowed_model,
)
from server.tournament_agent.clients.opencode import (
    ChatCompletionResult,
    OpenCodeGoClient,
    OpenCodeGoError,
    StreamChunk,
)
from server.tournament_agent.domain.format import (
    bracket_match_plan,
    canonical_stage_name,
    rewrite_sequential_pool_defs,
    snake_pool_seeds,
)
from server.tournament_agent.domain.scheduler import recommend_schedule
from server.tournament_agent.models import (
    AgentProposal,
    AgentQuestion,
    ProposalStatus,
    QuestionStatus,
    TournamentAgentMessage,
    TournamentAgentSession,
)
from server.tournament_agent.privacy.display import TokenTextStream, resolve_player_tokens
from server.tournament_agent.privacy.mask import (
    assert_safe_tool_payload,
    contains_forbidden_keys,
    scrub_user_text,
)
from server.tournament_agent.services.agent import (
    KEEP_RECENT_MESSAGES,
    TournamentAgentService,
    _compact_model_turns,
    looks_like_ack,
    looks_like_status_check,
    pending_proposals_prompt,
    verification_prompt,
)
from server.tournament_agent.services.proposals import (
    ProposalApplyError,
    apply_proposal,
    reject_proposal,
)
from server.tournament_agent.services.skills import SKILLS_DIR, load_skills, select_skills
from server.tournament_agent.tools import (
    HANDLERS,
    TOOL_DEFINITIONS,
    AskUserPause,
    ToolContext,
    ask_user,
    check_schedule_conflicts,
    dispatch_tool,
    find_roster_player,
    get_match_spirit,
    get_spirit_summary,
    get_tournament_overview,
    list_fields,
    list_missing_spirit_scores,
    list_proposals,
    list_stages,
    list_teams_seeding,
    propose_bulk_schedule,
    propose_create_bracket,
    propose_create_pool,
    propose_create_position_pool,
    propose_create_swiss_round,
    propose_delete_match,
    propose_delete_stage,
    propose_full_setup,
    propose_match_score,
    propose_recommended_schedule,
    propose_shift_schedule,
    propose_spirit_scores,
    propose_start_tournament,
    propose_update_match,
    propose_update_match_seeds,
)


class MaskTests(TestCase):
    def test_scrub_email_and_phone(self) -> None:
        text = "Contact coach@example.com or +91 98765 43210 please"
        scrubbed = scrub_user_text(text)
        self.assertNotIn("coach@example.com", scrubbed)
        self.assertIn("[REDACTED_EMAIL]", scrubbed)
        self.assertIn("[REDACTED_PHONE]", scrubbed)

    def test_does_not_scrub_iso_dates(self) -> None:
        text = "Schedule for Saturday 2026-08-01 with 75 minute games"
        scrubbed = scrub_user_text(text)
        self.assertIn("2026-08-01", scrubbed)
        self.assertNotIn("[REDACTED_PHONE]", scrubbed)

    def test_forbidden_keys_detected(self) -> None:
        payload = {"team_id": 1, "email": "a@b.com"}
        found = contains_forbidden_keys(payload)
        self.assertTrue(any("email" in f for f in found))
        with self.assertRaises(ValueError):
            assert_safe_tool_payload(payload)

    def test_safe_payload_ok(self) -> None:
        payload = {"team_id": 1, "team_name": "Disc Warriors", "seed": 3}
        assert_safe_tool_payload(payload)


class CatalogTests(TestCase):
    def test_default_and_allowlist(self) -> None:
        self.assertEqual(default_model_id(), "glm-5.2")
        self.assertTrue(is_allowed_model("glm-5.2"))
        self.assertTrue(is_allowed_model("gpt-5.6-luna"))
        self.assertTrue(is_allowed_model("minimax-m3"))
        self.assertTrue(is_allowed_model("hy3"))
        luna = get_model("gpt-5.6-luna")
        assert luna is not None
        self.assertEqual(luna.api_style, "responses")
        self.assertFalse(is_allowed_model("qwen3.7-plus"))
        self.assertFalse(is_allowed_model("deepseek-v4-pro"))
        self.assertFalse(is_allowed_model("gpt-4o"))

    def test_value_score_prefers_quota_when_scores_close(self) -> None:
        from server.tournament_agent.catalog import recommend_balanced_default, value_score

        # Near-tied capability: higher quota should win the balanced pick.
        self.assertGreater(value_score(90.0, "minimax-m3"), value_score(90.0, "glm-5.2"))
        results = {
            "glm-5.2": {"suite_score": 92.4, "pass_hat_k": 0.5, "mean_latency_s": 15.0},
            "minimax-m3": {"suite_score": 91.8, "pass_hat_k": 0.5, "mean_latency_s": 8.0},
        }
        self.assertEqual(recommend_balanced_default(results), "minimax-m3")


class SchemaTests(TestCase):
    def test_proposal_schema_keeps_player_names(self) -> None:
        from server.tournament_agent.schema import ProposalSchema

        parsed = ProposalSchema(
            id=1,
            tool_name="propose_spirit_scores",
            summary="Spirit",
            payload={"team_1_received": {"mvp_id": 12}},
            player_names={"12": "Priya Nair"},
            status="pending",
            created_at="2026-08-01T00:00:00",
        )
        dumped = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()
        self.assertEqual(dumped["player_names"], {"12": "Priya Nair"})


class TournamentAgentToolTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="staff1", is_staff=True)
        self.event = create_event(title="Test Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        self.team_a = Team.objects.create(name="Alpha", slug="alpha-ta")
        self.team_b = Team.objects.create(name="Beta", slug="beta-ta")
        self.team_c = Team.objects.create(name="Gamma", slug="gamma-ta")
        self.team_d = Team.objects.create(name="Delta", slug="delta-ta")
        seeding = {
            "1": self.team_a.id,
            "2": self.team_b.id,
            "3": self.team_c.id,
            "4": self.team_d.id,
        }
        self.tournament.initial_seeding = seeding
        self.tournament.current_seeding = seeding
        self.tournament.save()
        self.tournament.teams.set([self.team_a, self.team_b, self.team_c, self.team_d])
        TournamentField.objects.create(tournament=self.tournament, name="Field 1")
        self.session = TournamentAgentSession.objects.create(
            user=self.user, tournament=self.tournament, model_id=default_model_id()
        )
        self.ctx = ToolContext(session=self.session, tournament=self.tournament)

    def test_overview_and_seeding_safe(self) -> None:
        overview = get_tournament_overview(self.ctx)
        self.assertEqual(overview["tournament_id"], self.tournament.id)
        self.assertEqual(overview["team_count"], 4)
        assert_safe_tool_payload(overview)
        seeding = list_teams_seeding(self.ctx)
        self.assertEqual(len(seeding["seeding"]), 4)
        self.assertEqual(seeding["snake_draft"]["2_pools"]["A"], [1, 4])
        self.assertEqual(seeding["snake_draft"]["2_pools"]["B"], [2, 3])
        assert_safe_tool_payload(seeding)
        fields = list_fields(self.ctx)
        self.assertEqual(len(fields["fields"]), 1)

    def test_list_proposals_is_empty_when_nothing_is_pending(self) -> None:
        result = list_proposals(self.ctx)
        self.assertEqual(result["pending"], [])
        self.assertEqual(result["count"], 0)
        assert_safe_tool_payload(result)
        self.assertEqual(get_tournament_overview(self.ctx)["pending_proposal_count"], 0)

    def test_list_proposals_returns_pending_and_looks_up_missing_ids(self) -> None:
        pending = AgentProposal.objects.create(
            session=self.session,
            tool_name="propose_delete_stage",
            summary="Delete pool A",
            payload={"stage": "pool", "stage_id": 1},
            status=ProposalStatus.PENDING,
        )
        expired = AgentProposal.objects.create(
            session=self.session,
            tool_name="propose_delete_stage",
            summary="Delete pool B",
            payload={"stage": "pool", "stage_id": 2},
            status=ProposalStatus.EXPIRED,
        )

        listed = list_proposals(self.ctx)
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["pending"][0]["id"], pending.id)
        self.assertEqual(get_tournament_overview(self.ctx)["pending_proposal_count"], 1)

        missing = list_proposals(self.ctx, proposal_id=99999)
        self.assertFalse(missing["lookup"]["found"])
        self.assertEqual(missing["count"], 1)

        retired = list_proposals(self.ctx, proposal_id=expired.id)
        self.assertTrue(retired["lookup"]["found"])
        self.assertEqual(retired["lookup"]["status"], ProposalStatus.EXPIRED)
        self.assertIn("not pending", retired["lookup"]["message"])

    def test_pending_proposals_prompt_does_not_trust_chat(self) -> None:
        self.assertIn("None.", pending_proposals_prompt(self.session))
        AgentProposal.objects.create(
            session=self.session,
            tool_name="propose_create_field",
            summary="Create field Extra",
            payload={"name": "Extra"},
            status=ProposalStatus.PENDING,
        )
        text = pending_proposals_prompt(self.session)
        self.assertIn("propose_create_field", text)
        self.assertNotIn("\nNone.", text)
        system = TournamentAgentService(self.user)._build_model_messages(self.session)[0]["content"]
        self.assertIn("propose_create_field", system)
        self.assertIn("database — the only source of truth", system)

    def test_ack_and_status_prompts_demand_a_fresh_read(self) -> None:
        self.assertTrue(looks_like_ack("Done"))
        self.assertTrue(looks_like_ack("confirmed."))
        self.assertFalse(looks_like_ack("Done with pools, now schedule Saturday"))
        self.assertTrue(looks_like_status_check("Anything else?"))
        self.assertIn("list_stages", verification_prompt("Done"))
        self.assertIn("list_matches", verification_prompt("Anything else?"))
        self.assertEqual(verification_prompt("add a 1-4 bracket"), "")

        TournamentAgentMessage.objects.create(
            session=self.session,
            role="user",
            content="Done",
            payload={"masked_content": "Done"},
        )
        system = TournamentAgentService(self.user)._build_model_messages(self.session)[0]["content"]
        self.assertIn("not a database write", system)

    def test_ask_user_pauses(self) -> None:
        with self.assertRaises(AskUserPause) as cm:
            ask_user(
                self.ctx,
                prompt="Pools or Swiss?",
                selection_mode="single",
                options=[
                    {"id": "pools", "label": "Pools"},
                    {"id": "swiss", "label": "Swiss"},
                ],
            )
        q = cm.exception.question
        self.assertEqual(q.status, QuestionStatus.PENDING)
        self.assertEqual(len(q.options), 2)
        self.assertTrue(q.allow_other)

    def test_propose_and_confirm_pool(self) -> None:
        result = propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2])
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        self.assertEqual(proposal.status, ProposalStatus.PENDING)
        applied = apply_proposal(proposal)
        self.assertIn("pool_id", applied)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ProposalStatus.CONFIRMED)
        self.assertEqual(proposal.last_error, "")

    def test_create_bracket_lists_the_push_in_match(self) -> None:
        result = propose_create_bracket(self.ctx, name="1-4", sequence_number=1)
        self.assertIn("3rd Place", result["summary"])
        self.assertIn("3v4", result["summary"])
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        pairs = [
            (row["placeholder_seed_1"], row["placeholder_seed_2"])
            for row in proposal.payload["matches"]
        ]
        self.assertEqual(pairs, [(1, 4), (2, 3), (1, 2), (3, 4)])
        applied = apply_proposal(proposal)
        self.assertIn("bracket_id", applied)
        names = list(
            Match.objects.filter(bracket_id=applied["bracket_id"])
            .order_by("sequence_number", "placeholder_seed_1")
            .values_list("name", flat=True)
        )
        self.assertIn("3rd Place", names)

    def test_update_match_seeds_rewrites_bracket_pairings(self) -> None:
        applied = apply_proposal(
            AgentProposal.objects.get(
                id=propose_create_bracket(self.ctx, name="1-4", sequence_number=1)["proposal_id"]
            )
        )
        first_round = list(
            Match.objects.filter(bracket_id=applied["bracket_id"], sequence_number=1).order_by(
                "placeholder_seed_1"
            )
        )
        self.assertEqual(
            [(m.placeholder_seed_1, m.placeholder_seed_2) for m in first_round],
            [(1, 4), (2, 3)],
        )
        result = propose_update_match_seeds(
            self.ctx,
            updates=[
                {"match_id": first_round[0].id, "seed_1": 1, "seed_2": 3},
                {"match_id": first_round[1].id, "seed_1": 2, "seed_2": 4},
            ],
        )
        apply_proposal(AgentProposal.objects.get(id=result["proposal_id"]))
        first_round[0].refresh_from_db()
        first_round[1].refresh_from_db()
        self.assertEqual(
            (first_round[0].placeholder_seed_1, first_round[0].placeholder_seed_2), (1, 3)
        )
        self.assertEqual(
            (first_round[1].placeholder_seed_1, first_round[1].placeholder_seed_2), (2, 4)
        )
        later = {
            (m.placeholder_seed_1, m.placeholder_seed_2)
            for m in Match.objects.filter(bracket_id=applied["bracket_id"], sequence_number=2)
        }
        self.assertEqual(later, {(1, 2), (3, 4)})

    def test_update_match_seeds_refuses_a_doubled_seed(self) -> None:
        apply_proposal(
            AgentProposal.objects.get(
                id=propose_create_bracket(self.ctx, name="1-4", sequence_number=1)["proposal_id"]
            )
        )
        match = Match.objects.get(
            tournament=self.tournament, placeholder_seed_1=1, placeholder_seed_2=4
        )
        result = propose_update_match_seeds(
            self.ctx, updates=[{"match_id": match.id, "seed_1": 1, "seed_2": 3}]
        )
        with self.assertRaises(ProposalApplyError) as cm:
            apply_proposal(AgentProposal.objects.get(id=result["proposal_id"]))
        self.assertIn("Seed 3", str(cm.exception))

    def test_update_match_requires_both_seeds(self) -> None:
        result = propose_update_match(self.ctx, match_id=1, seed_1=1)
        self.assertIn("error", result)
        self.assertNotIn("proposal_id", result)

    def test_reject_proposal(self) -> None:
        result = propose_create_pool(self.ctx, name="B", sequence_number=2, seeding=[3, 4])
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        reject_proposal(proposal)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ProposalStatus.REJECTED)

    def test_recommend_schedule_places_matches(self) -> None:
        propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        proposal = AgentProposal.objects.filter(session=self.session).latest("id")
        apply_proposal(proposal)
        result = recommend_schedule(
            tournament=self.tournament,
            start_date="2026-08-01",
            duration_mins=75,
            field_ids=None,
        )
        self.assertGreater(len(result["assignments"]), 0)
        field_times = {(a["field_id"], a["time"]) for a in result["assignments"]}
        self.assertEqual(len(field_times), len(result["assignments"]))
        self.assertEqual(result["meta"].get("start_date"), "2026-08-01")

    def test_recommended_schedule_does_not_propose_a_partial_grid(self) -> None:
        propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        apply_proposal(AgentProposal.objects.filter(session=self.session).latest("id"))
        result = propose_recommended_schedule(
            self.ctx,
            start_date="2026-08-01",
            day_start_hour=9,
            day_end_hour=11,
        )
        self.assertIn("error", result)
        self.assertNotIn("proposal_id", result)
        self.assertGreater(result.get("unplaced", 0), 0)
        self.assertFalse(
            AgentProposal.objects.filter(tool_name="propose_recommended_schedule").exists()
        )


class SnakeAndBracketConventionTests(TestCase):
    """India Ultimate defaults the model used to invent: snake pools, full placement brackets."""

    def test_snake_two_and_four_pools(self) -> None:
        self.assertEqual(snake_pool_seeds(8, 2), [[1, 4, 5, 8], [2, 3, 6, 7]])
        self.assertEqual(
            snake_pool_seeds(16, 4),
            [
                [1, 8, 9, 16],
                [2, 7, 10, 15],
                [3, 6, 11, 14],
                [4, 5, 12, 13],
            ],
        )
        self.assertEqual(
            snake_pool_seeds(12, 4),
            [[1, 8, 9], [2, 7, 10], [3, 6, 11], [4, 5, 12]],
        )

    def test_one_four_bracket_includes_third_place(self) -> None:
        plan = bracket_match_plan("1-4")
        pairs = [(row["placeholder_seed_1"], row["placeholder_seed_2"]) for row in plan]
        self.assertEqual(pairs, [(1, 4), (2, 3), (1, 2), (3, 4)])
        self.assertEqual(
            [row["name"] for row in plan],
            ["Semi Finals", "Semi Finals", "Finals", "3rd Place"],
        )

    def test_rewrite_sequential_pool_defs_to_snake(self) -> None:
        rewritten = rewrite_sequential_pool_defs(
            [
                {"name": "A", "seeding": [1, 2, 3, 4]},
                {"name": "B", "seeding": [5, 6, 7, 8]},
            ],
            team_count=8,
        )
        self.assertEqual(rewritten[0]["seeding"], [1, 4, 5, 8])
        self.assertEqual(rewritten[1]["seeding"], [2, 3, 6, 7])


class FormatConventionToolTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="staff-format", is_staff=True)
        self.event = create_event(title="Format Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        self.teams = [Team.objects.create(name=f"Fmt {i}", slug=f"fmt-{i}") for i in range(1, 9)]
        self.tournament.teams.set(self.teams)
        seeding = {str(i): team.id for i, team in enumerate(self.teams, start=1)}
        self.tournament.initial_seeding = seeding
        self.tournament.current_seeding = seeding
        self.tournament.save()
        self.session = TournamentAgentSession.objects.create(
            user=self.user, tournament=self.tournament, model_id=default_model_id()
        )
        self.ctx = ToolContext(session=self.session, tournament=self.tournament)

    def test_sequential_pool_seeds_are_refused(self) -> None:
        result = propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        self.assertNotIn("proposal_id", result)
        self.assertIn("snake", result["error"].lower())
        self.assertEqual(result["snake_draft"]["A"], [1, 4, 5, 8])
        self.assertEqual(result["snake_draft"]["B"], [2, 3, 6, 7])
        self.assertFalse(AgentProposal.objects.filter(session=self.session).exists())

    def test_snake_pool_seeds_are_accepted(self) -> None:
        result = propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 4, 5, 8])
        self.assertIn("proposal_id", result)
        apply_proposal(AgentProposal.objects.get(id=result["proposal_id"]))
        pool = Pool.objects.get(tournament=self.tournament, name="A")
        self.assertEqual(sorted(map(int, pool.initial_seeding.keys())), [1, 4, 5, 8])

    def test_full_setup_rewrites_sequential_pools_to_snake(self) -> None:
        result = propose_full_setup(
            self.ctx,
            format="pools",
            pool_defs=[
                {"name": "A", "sequence_number": 1, "seeding": [1, 2, 3, 4]},
                {"name": "B", "sequence_number": 2, "seeding": [5, 6, 7, 8]},
            ],
            bracket_names=["1-4", "5-8"],
        )
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        self.assertEqual(proposal.payload["pool_defs"][0]["seeding"], [1, 4, 5, 8])
        self.assertEqual(proposal.payload["pool_defs"][1]["seeding"], [2, 3, 6, 7])

    def test_pool_names_drop_the_pool_prefix(self) -> None:
        self.assertEqual(canonical_stage_name("Pool A"), "A")
        self.assertEqual(canonical_stage_name("Swiss B"), "B")
        result = propose_create_pool(self.ctx, name="Pool A", sequence_number=1, seeding=[1, 4])
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        self.assertEqual(proposal.payload["name"], "A")
        apply_proposal(proposal)
        self.assertTrue(Pool.objects.filter(tournament=self.tournament, name="A").exists())

        full = propose_full_setup(
            self.ctx,
            format="pools",
            pool_defs=[
                {"name": "Pool A", "sequence_number": 1, "seeding": [1, 4]},
                {"name": "Pool B", "sequence_number": 2, "seeding": [2, 3]},
            ],
            bracket_names=["1-4"],
        )
        names = [
            row["name"]
            for row in AgentProposal.objects.get(id=full["proposal_id"]).payload["pool_defs"]
        ]
        self.assertEqual(names, ["A", "B"])

    def test_seeding_read_includes_snake_tables(self) -> None:
        seeding = list_teams_seeding(self.ctx)
        self.assertEqual(seeding["snake_draft"]["2_pools"]["A"], [1, 4, 5, 8])
        self.assertEqual(seeding["snake_draft"]["2_pools"]["B"], [2, 3, 6, 7])
        assert_safe_tool_payload(seeding)


class EvalScoringTests(TestCase):
    def test_must_not_ask_penalizes_overask(self) -> None:
        from server.tournament_agent.evals import TrajectoryTrace, score_case

        case = {
            "id": "t",
            "gold_tools": ["propose_recommended_schedule"],
            "forbidden_tools": ["ask_user"],
            "expect_state": {"must_not_ask_user": True, "min_proposals": 1},
            "pass_threshold": 80,
        }
        trace = TrajectoryTrace(
            tool_calls=[{"name": "ask_user"}],
            asked_user=True,
            proposals=[],
            steps=1,
        )
        scored = score_case(case, trace, expect_met=False)
        self.assertEqual(scored.scores["clarification"], 0.0)
        self.assertFalse(scored.passed)

    def test_schedule_payload_checks(self) -> None:
        from server.tournament_agent.evals import TrajectoryTrace, score_case

        case = {
            "id": "t",
            "gold_tools": ["propose_recommended_schedule"],
            "expect_state": {
                "min_proposals": 1,
                "proposal_tools": ["propose_recommended_schedule"],
                "schedule_start_date": "2026-08-01",
                "schedule_duration_mins": 75,
                "min_schedule_assignments": 2,
            },
            "pass_threshold": 80,
        }
        good = TrajectoryTrace(
            tool_calls=[{"name": "propose_recommended_schedule"}],
            proposals=[
                {
                    "tool_name": "propose_bulk_schedule",
                    "payload": {
                        "assignments": [
                            {"time": "2026-08-01T09:00:00", "duration_mins": 75},
                            {"time": "2026-08-01T10:30:00", "duration_mins": 75},
                        ],
                        "meta": {
                            "start_date": "2026-08-01",
                            "duration_mins": 75,
                        },
                    },
                }
            ],
            steps=2,
        )
        scored = score_case(case, good, expect_met=True)
        self.assertTrue(scored.passed)
        self.assertGreaterEqual(scored.overall, 80.0)

    def test_stage_order_violations_fail_the_case(self) -> None:
        from server.tournament_agent.evals import TrajectoryTrace, score_case

        case = {
            "id": "t",
            "gold_tools": ["propose_recommended_schedule"],
            "expect_state": {
                "must_not_ask_user": True,
                "min_proposals": 1,
                "no_stage_order_violations": True,
                "match_ranks": {1: 0, 2: 2},
            },
            "pass_threshold": 80,
        }
        overlapping = TrajectoryTrace(
            tool_calls=[{"name": "propose_recommended_schedule"}],
            proposals=[
                {
                    "tool_name": "propose_recommended_schedule",
                    "payload": {
                        "assignments": [
                            {
                                "match_id": 1,
                                "time": "2026-08-01T07:00:00",
                                "duration_mins": 75,
                            },
                            {
                                "match_id": 2,
                                "time": "2026-08-01T07:00:00",
                                "duration_mins": 75,
                            },
                        ]
                    },
                }
            ],
            steps=1,
        )
        scored = score_case(case, overlapping, expect_met=True)
        self.assertFalse(scored.passed)
        self.assertTrue(any("Stage order" in note for note in scored.notes))

        sequenced = TrajectoryTrace(
            tool_calls=[{"name": "propose_recommended_schedule"}],
            proposals=[
                {
                    "tool_name": "propose_recommended_schedule",
                    "payload": {
                        "assignments": [
                            {
                                "match_id": 1,
                                "time": "2026-08-01T07:00:00",
                                "duration_mins": 75,
                            },
                            {
                                "match_id": 2,
                                "time": "2026-08-01T08:15:00",
                                "duration_mins": 75,
                            },
                        ]
                    },
                }
            ],
            steps=1,
        )
        scored_ok = score_case(case, sequenced, expect_met=True)
        self.assertTrue(scored_ok.passed)

    def test_recommend_default_breaks_ties_by_latency(self) -> None:
        from server.tournament_agent.evals import recommend_default

        # Same score: higher Go quota (hy3 4300 vs glm 880) wins value ranking.
        results = {
            "glm-5.2": {
                "suite_score": 90.0,
                "pass_hat_k": 1.0,
                "mean_latency_s": 8.0,
            },
            "hy3": {
                "suite_score": 90.0,
                "pass_hat_k": 1.0,
                "mean_latency_s": 20.0,
            },
        }
        self.assertEqual(recommend_default(results), "hy3")


class TournamentAgentServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="staff2", is_staff=True)
        self.event = create_event(title="Svc Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        self.service = TournamentAgentService(self.user)

    def test_rejects_unknown_model(self) -> None:
        with self.assertRaises(ValueError):
            self.service.get_or_create_session(self.tournament.id, model_id="nope")

    def test_answer_question_flow_with_mock_client(self) -> None:
        session = self.service.get_or_create_session(self.tournament.id)
        q = AgentQuestion.objects.create(
            session=session,
            prompt="Duration?",
            selection_mode="single",
            options=[
                {"id": "75", "label": "75 min"},
                {"id": "90", "label": "90 min"},
            ],
            status=QuestionStatus.PENDING,
        )
        mock_result = MagicMock()
        mock_result.content = "Got it, using 75 minutes."
        mock_result.tool_calls = []
        with patch.object(self.service.client, "chat", return_value=mock_result):
            out = self.service.answer_question(session, q.id, selected_ids=["75"])
        self.assertIn("75", out["response"])
        q.refresh_from_db()
        self.assertEqual(q.status, QuestionStatus.ANSWERED)

    def test_cancel_question_without_allow_skip(self) -> None:
        session = self.service.get_or_create_session(self.tournament.id)
        q = AgentQuestion.objects.create(
            session=session,
            prompt="Pools or Swiss?",
            selection_mode="single",
            options=[
                {"id": "pools", "label": "Pools"},
                {"id": "swiss", "label": "Swiss"},
            ],
            allow_skip=False,
            status=QuestionStatus.PENDING,
        )
        with patch.object(self.service.client, "chat") as chat:
            out = self.service.answer_question(session, q.id, selected_ids=[], skip=True)
        chat.assert_not_called()
        self.assertIn("What would you like to do next?", out["response"])
        q.refresh_from_db()
        self.assertEqual(q.status, QuestionStatus.SKIPPED)
        self.assertTrue((q.answer or {}).get("cancelled"))

    def test_skip_does_not_start_another_model_turn(self) -> None:
        session = self.service.get_or_create_session(self.tournament.id)
        q = AgentQuestion.objects.create(
            session=session,
            prompt="Pools or Swiss?",
            selection_mode="single",
            options=[
                {"id": "pools", "label": "Pools"},
                {"id": "swiss", "label": "Swiss"},
            ],
            status=QuestionStatus.PENDING,
        )
        with patch.object(self.service.client, "chat") as chat:
            out = self.service.answer_question(session, q.id, selected_ids=[], skip=True)
        chat.assert_not_called()
        self.assertIn("What would you like to do next?", out["response"])
        q.refresh_from_db()
        self.assertEqual(q.status, QuestionStatus.SKIPPED)
        self.assertIsNone(out["pending_question"])
        hist = self.service.history(session)
        kinds = [m["message_kind"] for m in hist["messages"]]
        self.assertIn("answer", kinds)

    def test_typed_answer_without_selecting_an_option(self) -> None:
        session = self.service.get_or_create_session(self.tournament.id)
        q = AgentQuestion.objects.create(
            session=session,
            prompt="How many pools?",
            selection_mode="single",
            options=[
                {"id": "2", "label": "2"},
                {"id": "4", "label": "4"},
            ],
            allow_other=False,
            status=QuestionStatus.PENDING,
        )
        mock_result = MagicMock()
        mock_result.content = "Three pools it is."
        mock_result.tool_calls = []
        with patch.object(self.service.client, "chat", return_value=mock_result):
            out = self.service.answer_question(
                session, q.id, selected_ids=[], other_text="3 pools of 4"
            )
        self.assertIn("Three pools", out["response"])
        q.refresh_from_db()
        self.assertEqual(q.status, QuestionStatus.ANSWERED)
        self.assertEqual((q.answer or {}).get("other_text"), "3 pools of 4")

    def test_history_attaches_a_question_snapshot(self) -> None:
        session = self.service.get_or_create_session(self.tournament.id)
        q = AgentQuestion.objects.create(
            session=session,
            prompt="Pools or Swiss?",
            selection_mode="single",
            options=[
                {"id": "pools", "label": "Pools"},
                {"id": "swiss", "label": "Swiss"},
            ],
            status=QuestionStatus.PENDING,
        )
        TournamentAgentMessage.objects.create(
            session=session,
            role="assistant",
            content="Pools or Swiss?",
            message_kind="question",
            payload={"question_id": q.id},
        )
        hist = self.service.history(session)
        snap = hist["messages"][0]["payload"]["question_snapshot"]
        self.assertEqual(snap["prompt"], "Pools or Swiss?")
        self.assertEqual(len(snap["options"]), 2)

    def test_short_history_is_replayed_in_full(self) -> None:
        session = self.service.get_or_create_session(self.tournament.id)
        TournamentAgentMessage.objects.create(session=session, role="user", content="list fields")
        TournamentAgentMessage.objects.create(
            session=session, role="assistant", content="Field 1 is on the list."
        )
        messages = self.service._build_model_messages(session)
        roles = [m["role"] for m in messages]
        self.assertEqual(roles, ["system", "user", "assistant"])
        self.assertNotIn("Earlier conversation (compacted)", messages[0]["content"])
        self.assertEqual(messages[1]["content"], "list fields")
        self.assertEqual(messages[2]["content"], "Field 1 is on the list.")

    def test_long_history_is_compacted_for_the_model_not_the_ui(self) -> None:
        session = self.service.get_or_create_session(self.tournament.id)
        extra = KEEP_RECENT_MESSAGES + 4
        for i in range(extra):
            TournamentAgentMessage.objects.create(
                session=session, role="user", content=f"old user {i} secret-detail-{i}"
            )
            TournamentAgentMessage.objects.create(
                session=session, role="assistant", content=f"old reply {i}"
            )
        TournamentAgentMessage.objects.create(
            session=session, role="user", content="schedule Saturday"
        )
        TournamentAgentMessage.objects.create(
            session=session, role="assistant", content="Here is a plan."
        )

        model_msgs = self.service._build_model_messages(session)
        self.assertEqual(model_msgs[0]["role"], "system")
        self.assertIn("Earlier conversation (compacted)", model_msgs[0]["content"])
        self.assertIn("old user 0", model_msgs[0]["content"])
        # Recent turns stay as real messages; the oldest ones are digest-only.
        recent_text = " ".join(m["content"] for m in model_msgs[1:])
        self.assertIn("schedule Saturday", recent_text)
        self.assertNotIn("old user 0 secret-detail-0", recent_text)
        self.assertLessEqual(len(model_msgs) - 1, KEEP_RECENT_MESSAGES)

        ui = self.service.history(session)
        self.assertGreater(len(ui["messages"]), KEEP_RECENT_MESSAGES)

    def test_compact_helper_leaves_short_transcripts_alone(self) -> None:
        turns = [
            {"role": "user", "content": "pools?"},
            {"role": "assistant", "content": "two of four"},
        ]
        digest, recent = _compact_model_turns(turns)
        self.assertEqual(digest, "")
        self.assertEqual(recent, turns)


class NewProposalToolTests(TestCase):
    """Field and cross-pool proposal tools end-to-end."""

    def setUp(self) -> None:
        self.user = User.objects.create(username="staff3", is_staff=True)
        self.event = create_event(title="Field Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        self.teams = [
            Team.objects.create(name=f"Team NP{i}", slug=f"team-np{i}") for i in range(1, 5)
        ]
        self.tournament.teams.set(self.teams)
        seeding = {str(i + 1): team.id for i, team in enumerate(self.teams)}
        self.tournament.initial_seeding = seeding
        self.tournament.current_seeding = seeding
        self.tournament.save()
        self.session = TournamentAgentSession.objects.create(
            user=self.user, tournament=self.tournament, model_id=default_model_id()
        )
        self.ctx = ToolContext(session=self.session, tournament=self.tournament)

    def _apply(self, result: dict[str, Any]) -> dict[str, Any]:
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        return apply_proposal(proposal)

    def test_create_field_proposal_applies(self) -> None:
        from server.tournament_agent.tools import propose_create_field

        result = propose_create_field(self.ctx, name="  Field 3 ")
        applied = self._apply(result)
        field = TournamentField.objects.get(id=applied["field_id"])
        self.assertEqual(field.name, "Field 3")
        self.assertEqual(field.tournament_id, self.tournament.id)

    def test_create_field_duplicate_name_rejected(self) -> None:
        from server.tournament_agent.services.proposals import ProposalApplyError
        from server.tournament_agent.tools import propose_create_field

        TournamentField.objects.create(tournament=self.tournament, name="Field 3")
        result = propose_create_field(self.ctx, name="field 3")
        with self.assertRaises(ProposalApplyError):
            self._apply(result)

    def test_update_field_renames_and_sets_broadcast(self) -> None:
        from server.tournament_agent.tools import propose_create_field, propose_update_field

        created = self._apply(propose_create_field(self.ctx, name="Field 3"))
        applied = self._apply(
            propose_update_field(
                self.ctx, field_id=created["field_id"], name="Main", is_broadcasted=True
            )
        )
        field = TournamentField.objects.get(id=applied["field_id"])
        self.assertEqual(field.name, "Main")
        self.assertTrue(field.is_broadcasted)

    def test_update_field_clears_address(self) -> None:
        from server.tournament_agent.tools import propose_update_field

        field = TournamentField.objects.create(
            tournament=self.tournament, name="Field 3", address="KG Farms"
        )
        self._apply(propose_update_field(self.ctx, field_id=field.id, address=""))
        field.refresh_from_db()
        self.assertIsNone(field.address)

    def test_update_field_duplicate_name_rejected_before_proposing(self) -> None:
        from server.tournament_agent.tools import propose_update_field

        existing = TournamentField.objects.create(tournament=self.tournament, name="Field 3")
        TournamentField.objects.create(tournament=self.tournament, name="Field 4")
        result = propose_update_field(self.ctx, field_id=existing.id, name="field 4")
        self.assertIn("error", result)
        self.assertFalse(AgentProposal.objects.filter(tool_name="propose_update_field").exists())

    def test_update_field_missing_does_not_propose(self) -> None:
        from server.tournament_agent.tools import propose_update_field

        result = propose_update_field(self.ctx, field_id=99999, name="Nope")
        self.assertIn("error", result)
        self.assertFalse(AgentProposal.objects.filter(tool_name="propose_update_field").exists())

    def test_delete_field_applies(self) -> None:
        from server.tournament_agent.tools import propose_create_field, propose_delete_field

        created = self._apply(propose_create_field(self.ctx, name="Spare"))
        applied = self._apply(propose_delete_field(self.ctx, field_id=created["field_id"]))
        self.assertEqual(applied["name"], "Spare")
        self.assertFalse(TournamentField.objects.filter(id=created["field_id"]).exists())

    def test_delete_field_refused_when_matches_assigned(self) -> None:
        from server.tournament_agent.tools import (
            propose_create_field,
            propose_create_pool,
            propose_delete_field,
            propose_update_match,
        )

        field = self._apply(propose_create_field(self.ctx, name="Field 3"))
        self._apply(propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2]))
        match = Match.objects.get(tournament=self.tournament)
        self._apply(propose_update_match(self.ctx, match_id=match.id, field_id=field["field_id"]))

        result = propose_delete_field(self.ctx, field_id=field["field_id"])
        self.assertIn("error", result)
        self.assertFalse(AgentProposal.objects.filter(tool_name="propose_delete_field").exists())
        self.assertTrue(TournamentField.objects.filter(id=field["field_id"]).exists())

    def test_delete_field_refused_at_apply_if_match_added_later(self) -> None:
        from server.tournament_agent.services.proposals import ProposalApplyError
        from server.tournament_agent.tools import (
            propose_create_field,
            propose_create_pool,
            propose_delete_field,
            propose_update_match,
        )

        field = self._apply(propose_create_field(self.ctx, name="Field 3"))
        result = propose_delete_field(self.ctx, field_id=field["field_id"])
        self._apply(propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2]))
        match = Match.objects.get(tournament=self.tournament)
        self._apply(propose_update_match(self.ctx, match_id=match.id, field_id=field["field_id"]))
        with self.assertRaises(ProposalApplyError):
            self._apply(result)
        self.assertTrue(TournamentField.objects.filter(id=field["field_id"]).exists())

    def test_delete_field_dispatch_accepts_id_alias(self) -> None:
        from server.tournament_agent.tools import propose_create_field

        created = self._apply(propose_create_field(self.ctx, name="Alias"))
        result = dispatch_tool(self.ctx, "propose_delete_field", {"id": created["field_id"]})
        self.assertIn("proposal_id", result)

    def test_cross_pool_matches_require_stage(self) -> None:
        from server.tournament_agent.services.proposals import ProposalApplyError
        from server.tournament_agent.tools import propose_create_cross_pool_matches

        result = propose_create_cross_pool_matches(self.ctx, seed_pairs=[[1, 3]])
        with self.assertRaises(ProposalApplyError):
            self._apply(result)

    def test_cross_pool_matches_created_from_seed_pairs(self) -> None:
        from server.tournament.models import CrossPool, Match
        from server.tournament_agent.tools import (
            propose_create_cross_pool,
            propose_create_cross_pool_matches,
        )

        self._apply(propose_create_cross_pool(self.ctx))
        cross_pool = CrossPool.objects.get(tournament=self.tournament)

        result = propose_create_cross_pool_matches(self.ctx, seed_pairs=[[1, 3], [2, 4]])
        applied = self._apply(result)
        self.assertEqual(applied["count"], 2)

        matches = Match.objects.filter(cross_pool=cross_pool).order_by("id")
        self.assertEqual(matches.count(), 2)
        first = matches.first()
        assert first is not None
        self.assertEqual(first.name, "Cross Pool")
        self.assertEqual(first.status, Match.Status.YET_TO_FIX)
        self.assertEqual((first.placeholder_seed_1, first.placeholder_seed_2), (1, 3))

    def test_cross_pool_duplicate_pair_rejected(self) -> None:
        from server.tournament_agent.services.proposals import ProposalApplyError
        from server.tournament_agent.tools import (
            propose_create_cross_pool,
            propose_create_cross_pool_matches,
        )

        self._apply(propose_create_cross_pool(self.ctx))
        self._apply(propose_create_cross_pool_matches(self.ctx, seed_pairs=[[1, 3]]))
        result = propose_create_cross_pool_matches(self.ctx, seed_pairs=[[3, 1]])
        with self.assertRaises(ProposalApplyError):
            self._apply(result)

    def test_cross_pool_seed_out_of_range_rejected(self) -> None:
        from server.tournament_agent.services.proposals import ProposalApplyError
        from server.tournament_agent.tools import (
            propose_create_cross_pool,
            propose_create_cross_pool_matches,
        )

        self._apply(propose_create_cross_pool(self.ctx))
        result = propose_create_cross_pool_matches(self.ctx, seed_pairs=[[1, 9]])
        with self.assertRaises(ProposalApplyError):
            self._apply(result)


class ToolEventTests(TestCase):
    """Tool calls are persisted as tool_events on the assistant message."""

    def setUp(self) -> None:
        self.user = User.objects.create(username="staff4", is_staff=True)
        self.event = create_event(title="Events Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        self.service = TournamentAgentService(self.user)
        self.session = self.service.get_or_create_session(self.tournament.id)

    def _mock_round(self, content: str, tool_calls: list[dict[str, str]]) -> MagicMock:
        result = MagicMock()
        result.content = content
        result.tool_calls = tool_calls
        result.finish_reason = "tool_calls" if tool_calls else "stop"
        return result

    def test_tool_events_persisted_on_message(self) -> None:
        rounds = [
            self._mock_round(
                "",
                [{"name": "list_fields", "id": "tc1", "arguments": "{}"}],
            ),
            self._mock_round("Here are the fields.", []),
        ]
        with patch.object(self.service.client, "chat", side_effect=rounds):
            out = self.service.process_message(self.session, "show fields")

        self.assertEqual(len(out["tool_events"]), 1)
        event = out["tool_events"][0]
        self.assertEqual(event["name"], "list_fields")
        self.assertEqual(event["status"], "ok")
        self.assertIn("duration_ms", event)

        message = self.session.messages.filter(role="assistant").latest("created_at")
        self.assertEqual(len(message.payload["tool_events"]), 1)
        self.assertEqual(message.payload["tool_events"][0]["name"], "list_fields")

    def test_tool_error_is_recoverable(self) -> None:
        rounds = [
            self._mock_round(
                "",
                [
                    {
                        "name": "propose_create_pool",
                        "id": "tc1",
                        # Missing required args -> TypeError inside dispatch
                        "arguments": "{}",
                    }
                ],
            ),
            self._mock_round("That didn't work; I need pool details.", []),
        ]
        with patch.object(self.service.client, "chat", side_effect=rounds):
            out = self.service.process_message(self.session, "make a pool")

        self.assertEqual(out["tool_events"][0]["status"], "error")
        # The loop recovered and produced a final response instead of crashing
        self.assertIn("didn't work", out["response"])

    def test_proposal_events_tagged(self) -> None:
        args = '{"name": "A", "sequence_number": 1, "seeding": [1, 2]}'
        team_a = Team.objects.create(name="Evt A", slug="evt-a")
        team_b = Team.objects.create(name="Evt B", slug="evt-b")
        self.tournament.teams.set([team_a, team_b])
        self.tournament.initial_seeding = {"1": team_a.id, "2": team_b.id}
        self.tournament.current_seeding = {"1": team_a.id, "2": team_b.id}
        self.tournament.save()

        rounds = [
            self._mock_round(
                "",
                [{"name": "propose_create_pool", "id": "tc1", "arguments": args}],
            ),
            self._mock_round("Proposed pool A for you to confirm.", []),
        ]
        with patch.object(self.service.client, "chat", side_effect=rounds):
            out = self.service.process_message(self.session, "create pool A with seeds 1,2")

        event = out["tool_events"][0]
        self.assertEqual(event["status"], "proposal")
        self.assertIn("proposal_id", event)
        self.assertIn("Proposal #", event["summary"])


def _sse_response(lines: list[str]) -> MagicMock:
    """A fake httpx streaming response whose body is the given SSE lines."""
    resp = MagicMock()
    resp.status_code = 200
    resp.iter_lines.return_value = iter(lines)
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=resp)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _model_id_for_style(style: str) -> str:
    model = next((m for m in AGENT_MODELS if m.api_style == style), None)
    if model is None:
        raise AssertionError(f"no {style}-style model in the catalog")
    return model.id


class ProviderStreamParsingTests(TestCase):
    """chat_stream assembles deltas back into a ChatCompletionResult."""

    def _client(self) -> OpenCodeGoClient:
        return OpenCodeGoClient(api_key="test-key", base_url="https://example.invalid/v1")

    def test_default_model_is_covered_by_a_stream_parser(self) -> None:
        # The default model drives which parser production actually exercises.
        default = get_model(default_model_id())
        assert default is not None
        self.assertIn(default.api_style, {"openai", "anthropic"})

    def test_responses_chat_parses_function_calls(self) -> None:
        payload = {
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "list_fields",
                    "arguments": "{}",
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Checking fields"}],
                },
            ],
        }
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = payload
        resp.text = json.dumps(payload)
        http_client = MagicMock()
        http_client.__enter__.return_value = http_client
        http_client.__exit__.return_value = False
        http_client.post.return_value = resp
        client = self._client()
        with patch("httpx.Client", return_value=http_client):
            result = client.chat(
                model_id="gpt-5.6-luna",
                messages=[
                    {"role": "system", "content": "You are the agent."},
                    {"role": "user", "content": "schedule it"},
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "list_fields",
                            "description": "List fields",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            )
        self.assertEqual(result.content, "Checking fields")
        self.assertEqual(result.tool_calls[0]["name"], "list_fields")
        self.assertEqual(result.tool_calls[0]["id"], "call_1")
        url, _kwargs = http_client.post.call_args[0][0], http_client.post.call_args.kwargs
        self.assertTrue(str(url).endswith("/responses"))
        self.assertEqual(_kwargs["json"]["tools"][0]["name"], "list_fields")
        self.assertIn("You are the agent.", _kwargs["json"]["instructions"])

    def test_openai_stream_text_and_tool_calls(self) -> None:
        # Tool call name/arguments arrive split across deltas, keyed by index.
        lines = [
            'data: {"choices":[{"delta":{"content":"Check"}}]}',
            'data: {"choices":[{"delta":{"content":"ing pools"}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"tc_1",'
            '"function":{"name":"list_po"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"function":{"name":"ols","arguments":"{\\"tourna"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
            '"function":{"arguments":"ment_id\\": 7}"}}]}}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
            "data: [DONE]",
        ]
        client = self._client()
        with patch("httpx.Client.stream", return_value=_sse_response(lines)):
            chunks = list(
                client.chat_stream(
                    model_id=_model_id_for_style("openai"), messages=[{"role": "user"}]
                )
            )

        texts = [c.text for c in chunks if c.type == "text"]
        self.assertEqual(texts, ["Check", "ing pools"])

        result = chunks[-1].result
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.content, "Checking pools")
        self.assertEqual(result.finish_reason, "tool_calls")
        self.assertEqual(len(result.tool_calls), 1)
        # Fragments must be concatenated in arrival order, not overwritten.
        self.assertEqual(result.tool_calls[0]["name"], "list_pools")
        self.assertEqual(result.tool_calls[0]["id"], "tc_1")
        self.assertEqual(result.tool_calls[0]["arguments"], '{"tournament_id": 7}')

    def test_openai_stream_ignores_comments_and_bad_json(self) -> None:
        lines = [
            ": keep-alive",
            "",
            "data: {not json}",
            'data: {"choices":[{"delta":{"content":"ok"}}]}',
            "data: [DONE]",
            'data: {"choices":[{"delta":{"content":"after done"}}]}',
        ]
        client = self._client()
        with patch("httpx.Client.stream", return_value=_sse_response(lines)):
            chunks = list(
                client.chat_stream(
                    model_id=_model_id_for_style("openai"), messages=[{"role": "user"}]
                )
            )
        texts = [c.text for c in chunks if c.type == "text"]
        self.assertEqual(texts, ["ok"])

    def test_openai_stream_raises_on_error_payload(self) -> None:
        lines = ['data: {"error":{"message":"rate limited"}}']
        client = self._client()
        with (
            patch("httpx.Client.stream", return_value=_sse_response(lines)),
            self.assertRaises(OpenCodeGoError),
        ):
            list(
                client.chat_stream(
                    model_id=_model_id_for_style("openai"), messages=[{"role": "user"}]
                )
            )

    def test_openai_stream_raises_on_http_error(self) -> None:
        resp = MagicMock()
        resp.status_code = 429
        resp.encoding = "utf-8"
        resp.read.return_value = b"too many requests"
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=resp)
        ctx.__exit__ = MagicMock(return_value=False)
        client = self._client()
        with (
            patch("httpx.Client.stream", return_value=ctx),
            self.assertRaises(OpenCodeGoError) as caught,
        ):
            list(
                client.chat_stream(
                    model_id=_model_id_for_style("openai"), messages=[{"role": "user"}]
                )
            )
        self.assertIn("429", str(caught.exception))

    def test_anthropic_stream_text_and_tool_use(self) -> None:
        lines = [
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"text"}}',
            'data: {"type":"content_block_delta","index":0,'
            '"delta":{"type":"text_delta","text":"Making "}}',
            'data: {"type":"content_block_delta","index":0,'
            '"delta":{"type":"text_delta","text":"a pool"}}',
            'data: {"type":"content_block_start","index":1,'
            '"content_block":{"type":"tool_use","id":"tu_1","name":"propose_create_pool"}}',
            'data: {"type":"content_block_delta","index":1,'
            '"delta":{"type":"input_json_delta","partial_json":"{\\"name\\":"}}',
            'data: {"type":"content_block_delta","index":1,'
            '"delta":{"type":"input_json_delta","partial_json":"\\"A\\"}"}}',
            'data: {"type":"content_block_stop","index":1}',
            'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}',
        ]
        client = self._client()
        with patch("httpx.Client.stream", return_value=_sse_response(lines)):
            chunks = list(
                client.chat_stream(
                    model_id=_model_id_for_style("anthropic"), messages=[{"role": "user"}]
                )
            )

        texts = [c.text for c in chunks if c.type == "text"]
        self.assertEqual(texts, ["Making ", "a pool"])
        result = chunks[-1].result
        assert result is not None
        self.assertEqual(result.content, "Making a pool")
        self.assertEqual(result.finish_reason, "tool_use")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0]["name"], "propose_create_pool")
        self.assertEqual(result.tool_calls[0]["arguments"], '{"name":"A"}')


class AgentEventStreamTests(TestCase):
    """_run_agent_events emits the event sequence the UI renders from."""

    def setUp(self) -> None:
        self.user = User.objects.create(username="staff5", is_staff=True)
        self.event = create_event(title="Streaming Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        TournamentField.objects.create(tournament=self.tournament, name="Field 1")
        self.service = TournamentAgentService(self.user)
        self.session = self.service.get_or_create_session(self.tournament.id)

    def _mock_round(self, content: str, tool_calls: list[dict[str, str]]) -> MagicMock:
        result = MagicMock()
        result.content = content
        result.tool_calls = tool_calls
        result.finish_reason = "tool_calls" if tool_calls else "stop"
        return result

    def test_event_sequence_for_a_tool_turn(self) -> None:
        rounds = [
            self._mock_round("", [{"name": "list_fields", "id": "tc1", "arguments": "{}"}]),
            self._mock_round("Field 1 is your only field.", []),
        ]
        with patch.object(self.service.client, "chat", side_effect=rounds):
            events = list(self.service.process_message_events(self.session, "show fields"))

        types = [e["type"] for e in events]
        self.assertEqual(types.count("done"), 1)
        self.assertEqual(types[-1], "done")
        self.assertIn("tool_start", types)
        self.assertIn("tool_end", types)
        # tool_start must precede its tool_end so the UI can show a running row.
        self.assertLess(types.index("tool_start"), types.index("tool_end"))

        start = next(e for e in events if e["type"] == "tool_start")
        end = next(e for e in events if e["type"] == "tool_end")
        self.assertEqual(start["name"], "list_fields")
        self.assertEqual(start["index"], end["index"])
        self.assertEqual(end["status"], "ok")
        self.assertIn("duration_ms", end)

        done = events[-1]["payload"]
        self.assertEqual(done["response"], "Field 1 is your only field.")
        self.assertEqual(len(done["tool_events"]), 1)
        self.assertIn("message_id", done)

    def test_proposal_event_emitted_with_full_proposal(self) -> None:
        rounds = [
            self._mock_round(
                "",
                [
                    {
                        "name": "propose_create_field",
                        "id": "tc1",
                        "arguments": '{"name": "Field 2"}',
                    }
                ],
            ),
            self._mock_round("Proposed a new field.", []),
        ]
        with patch.object(self.service.client, "chat", side_effect=rounds):
            events = list(self.service.process_message_events(self.session, "add a field"))

        proposal_events = [e for e in events if e["type"] == "proposal"]
        self.assertEqual(len(proposal_events), 1)
        proposal = proposal_events[0]["proposal"]
        self.assertEqual(proposal["tool_name"], "propose_create_field")
        self.assertEqual(proposal["status"], "pending")
        self.assertIn("payload", proposal)
        # The proposal event must follow the tool_end that created it.
        types = [e["type"] for e in events]
        self.assertLess(types.index("tool_end"), types.index("proposal"))

    def test_plain_text_proposal_claim_is_nudged_until_a_tool_runs(self) -> None:
        # Models sometimes say "Proposal #N is live" without calling propose_*.
        # One nudge used to be enough to give up; staff then had nothing to Confirm.
        rounds = [
            self._mock_round("Proposal #12 is live and pending staff Confirm.", []),
            self._mock_round("Proposal #12 is live.", []),
            self._mock_round(
                "",
                [
                    {
                        "name": "propose_create_field",
                        "id": "tc1",
                        "arguments": '{"name": "Field 2"}',
                    }
                ],
            ),
            self._mock_round("Proposed a new field.", []),
        ]
        with patch.object(self.service.client, "chat", side_effect=rounds) as chat:
            events = list(self.service.process_message_events(self.session, "add a field"))

        self.assertGreaterEqual(chat.call_count, 3)
        nudge_seen = False
        for call in chat.call_args_list:
            for message in call.kwargs["messages"]:
                if message.get("role") != "user":
                    continue
                if "Plain text does not create a proposal" in (message.get("content") or ""):
                    nudge_seen = True
        self.assertTrue(nudge_seen)
        proposal_events = [e for e in events if e["type"] == "proposal"]
        self.assertEqual(len(proposal_events), 1)
        self.assertEqual(proposal_events[0]["proposal"]["tool_name"], "propose_create_field")

    def test_question_event_ends_the_turn(self) -> None:
        rounds = [
            self._mock_round(
                "",
                [
                    {
                        "name": "ask_user",
                        "id": "tc1",
                        "arguments": (
                            '{"prompt": "Pools or Swiss?", "selection_mode": "single",'
                            ' "options": [{"id": "pools", "label": "Pools"},'
                            ' {"id": "swiss", "label": "Swiss"}]}'
                        ),
                    }
                ],
            ),
        ]
        with patch.object(self.service.client, "chat", side_effect=rounds):
            events = list(self.service.process_message_events(self.session, "set it up"))

        types = [e["type"] for e in events]
        self.assertIn("question", types)
        self.assertEqual(types[-1], "done")
        question = next(e for e in events if e["type"] == "question")["question"]
        self.assertEqual(question["prompt"], "Pools or Swiss?")
        self.assertEqual(events[-1]["payload"]["pending_question"]["id"], question["id"])

    def test_sync_run_agent_still_returns_final_payload(self) -> None:
        rounds = [
            self._mock_round("", [{"name": "list_fields", "id": "tc1", "arguments": "{}"}]),
            self._mock_round("Done.", []),
        ]
        with patch.object(self.service.client, "chat", side_effect=rounds):
            out = self.service.process_message(self.session, "show fields")
        self.assertEqual(out["response"], "Done.")
        self.assertEqual(len(out["tool_events"]), 1)

    def test_streaming_mode_emits_text_deltas(self) -> None:
        streaming_service = TournamentAgentService(self.user, streaming=True)
        session = streaming_service.get_or_create_session(self.tournament.id)

        def tool_round(**kwargs: Any) -> Any:
            yield StreamChunk(type="text", text="Let me ")
            yield StreamChunk(type="text", text="check.")
            yield StreamChunk(
                type="result",
                result=ChatCompletionResult(
                    content="Let me check.",
                    tool_calls=[{"id": "t0", "name": "list_fields", "arguments": "{}"}],
                    raw={},
                    finish_reason="tool_calls",
                ),
            )

        def final_round(**kwargs: Any) -> Any:
            yield StreamChunk(type="text", text="Field 1 ")
            yield StreamChunk(type="text", text="is it.")
            yield StreamChunk(
                type="result",
                result=ChatCompletionResult(
                    content="Field 1 is it.", tool_calls=[], raw={}, finish_reason="stop"
                ),
            )

        with patch.object(
            streaming_service.client, "chat_stream", side_effect=[tool_round(), final_round()]
        ):
            events = list(streaming_service.process_message_events(session, "which fields?"))

        deltas = [e["text"] for e in events if e["type"] == "text_delta"]
        self.assertEqual(deltas, ["Let me ", "check.", "Field 1 ", "is it."])
        self.assertEqual(events[-1]["payload"]["response"], "Field 1 is it.")
        # Deltas must arrive before the tool runs, not batched at the end.
        types = [e["type"] for e in events]
        self.assertLess(types.index("text_delta"), types.index("tool_start"))

    def test_streaming_keeps_text_when_tool_round_content_is_empty(self) -> None:
        # Providers often strip <tool_call> text to empty content on the tool
        # round. Replacing the display with that would flash the blob then go
        # blank; leave the streamed text until the next round has real copy.
        streaming_service = TournamentAgentService(self.user, streaming=True)
        session = streaming_service.get_or_create_session(self.tournament.id)
        blob = "<tool_call><name>list_fields</name><arguments>{}</arguments></tool_call>"

        def fake_stream(**kwargs: Any) -> Any:
            yield StreamChunk(type="text", text=blob)
            yield StreamChunk(
                type="result",
                result=ChatCompletionResult(
                    content=None,
                    tool_calls=[{"id": "t0", "name": "list_fields", "arguments": "{}"}],
                    raw={},
                    finish_reason="tool_calls",
                ),
            )

        def second_round(**kwargs: Any) -> Any:
            yield StreamChunk(type="text", text="Field 1.")
            yield StreamChunk(
                type="result",
                result=ChatCompletionResult(
                    content="Field 1.", tool_calls=[], raw={}, finish_reason="stop"
                ),
            )

        with patch.object(
            streaming_service.client, "chat_stream", side_effect=[fake_stream(), second_round()]
        ):
            events = list(streaming_service.process_message_events(session, "fields?"))

        self.assertEqual([e for e in events if e["type"] == "text_replace"], [])
        self.assertTrue(any(e.get("text") == blob for e in events if e["type"] == "text_delta"))


class StreamEndpointTests(ApiBaseTestCase):
    """The SSE endpoint frames agent events as text/event-stream."""

    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        self.event = create_event(title="SSE Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        TournamentField.objects.create(tournament=self.tournament, name="Field 1")

    def _stream_round(self, content: str, tool_calls: list[dict[str, str]]) -> Any:
        """A chat_stream generator: text deltas then the assembled result."""

        def gen(**kwargs: Any) -> Any:
            if content:
                yield StreamChunk(type="text", text=content)
            yield StreamChunk(
                type="result",
                result=ChatCompletionResult(
                    content=content or None,
                    tool_calls=tool_calls,
                    raw={},
                    finish_reason="tool_calls" if tool_calls else "stop",
                ),
            )

        return gen()

    def _parse_sse(self, body: str) -> list[tuple[str, dict[str, Any]]]:
        frames: list[tuple[str, dict[str, Any]]] = []
        for block in body.split("\n\n"):
            name = ""
            data = ""
            for line in block.splitlines():
                if line.startswith("event: "):
                    name = line[len("event: ") :]
                elif line.startswith("data: "):
                    data = line[len("data: ") :]
            if name and data:
                frames.append((name, json.loads(data)))
        return frames

    def _post_stream(self, message: str) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
        response = self.client.post(
            "/api/tournament-agent/stream_message",
            data=json.dumps({"tournament_id": self.tournament.id, "message": message}),
            content_type="application/json",
        )
        chunks = cast(Iterator[bytes], cast(StreamingHttpResponse, response).streaming_content)
        body = b"".join(chunks).decode()
        return response, self._parse_sse(body)

    def test_stream_emits_framed_events_and_done(self) -> None:
        rounds = [
            self._stream_round("", [{"name": "list_fields", "id": "tc1", "arguments": "{}"}]),
            self._stream_round("You have 1 field.", []),
        ]
        with patch(
            "server.tournament_agent.clients.opencode.OpenCodeGoClient.chat_stream",
            side_effect=rounds,
        ):
            response, frames = self._post_stream("show fields")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        # Without this nginx buffers the whole turn and streaming does nothing.
        self.assertEqual(response["X-Accel-Buffering"], "no")

        names = [name for name, _ in frames]
        self.assertIn("tool_start", names)
        self.assertIn("tool_end", names)
        self.assertEqual(names[-1], "done")
        done = frames[-1][1]["payload"]
        self.assertEqual(done["response"], "You have 1 field.")

    def test_stream_reports_mid_turn_failure_as_error_frame(self) -> None:
        # Headers are already sent, so this cannot become a 500.
        with patch(
            "server.tournament_agent.clients.opencode.OpenCodeGoClient.chat_stream",
            side_effect=RuntimeError("provider exploded"),
        ):
            response, frames = self._post_stream("show fields")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(frames[-1][0], "error")
        self.assertIn("provider exploded", frames[-1][1]["message"])

    def test_stream_requires_staff(self) -> None:
        self.user.is_staff = False
        self.user.save()
        response, frames = self._post_stream("show fields")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(frames[-1][0], "error")

    def test_user_message_is_persisted_before_streaming_starts(self) -> None:
        rounds = [
            self._stream_round("Hi.", []),
            self._stream_round("Hi.", []),
            self._stream_round("Hi.", []),
        ]
        with patch(
            "server.tournament_agent.clients.opencode.OpenCodeGoClient.chat_stream",
            side_effect=rounds,
        ):
            self._post_stream("remember this")
        session = TournamentAgentSession.objects.get(user=self.user, tournament=self.tournament)
        self.assertTrue(session.messages.filter(role="user", content="remember this").exists())


class ProposalSafetyTests(TestCase):
    """Regression tests for the corruption paths fixed in the P0a hardening pass."""

    def setUp(self) -> None:
        self.user = User.objects.create(username="staff-safety", is_staff=True)
        self.event = create_event(title="Safety Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        teams = [Team.objects.create(name=f"Safety {i}", slug=f"safety-{i}") for i in range(1, 5)]
        seeding = {str(i): team.id for i, team in enumerate(teams, start=1)}
        self.tournament.initial_seeding = seeding
        self.tournament.current_seeding = seeding
        self.tournament.save()
        self.tournament.teams.set(teams)
        self.field = TournamentField.objects.create(tournament=self.tournament, name="Field 1")
        self.session = TournamentAgentSession.objects.create(
            user=self.user, tournament=self.tournament, model_id=default_model_id()
        )
        self.ctx = ToolContext(session=self.session, tournament=self.tournament)

    def _apply(self, result: dict[str, Any]) -> dict[str, Any]:
        return apply_proposal(AgentProposal.objects.get(id=result["proposal_id"]))

    def _completed_match(self) -> Match:
        self._apply(propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2]))
        match = Match.objects.get(tournament=self.tournament)
        match.status = Match.Status.COMPLETED
        match.save()
        return match

    def test_swiss_group_starts_on_round_one(self) -> None:
        # current_round=0 would make populate_fixtures skip the group forever.
        self._apply(
            propose_create_swiss_round(
                self.ctx, name="A", seeding=[1, 2, 3, 4], num_rounds=2, sequence_number=1
            )
        )
        self.assertEqual(SwissRound.objects.get(tournament=self.tournament).current_round, 1)

    def test_position_pool_results_start_empty(self) -> None:
        # Seed-keyed rows here collide with the team-keyed rows populate_fixtures
        # writes, which then blows up ranking on the first score.
        self._apply(
            propose_create_position_pool(self.ctx, name="E", sequence_number=1, seeding=[3, 4])
        )
        self.assertEqual(PositionPool.objects.get(tournament=self.tournament).results, {})

    def test_start_tournament_refuses_when_already_live(self) -> None:
        self._apply(propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2]))
        self._apply(propose_start_tournament(self.ctx))
        match = Match.objects.get(tournament=self.tournament)
        match.status = Match.Status.COMPLETED
        match.save()

        with self.assertRaises(ProposalApplyError):
            self._apply(propose_start_tournament(self.ctx))

        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.COMPLETED)

    def test_completed_match_cannot_be_rescheduled(self) -> None:
        match = self._completed_match()
        with self.assertRaises(ProposalApplyError):
            self._apply(
                propose_update_match(self.ctx, match_id=match.id, time="2026-08-01T09:00:00")
            )
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.COMPLETED)
        self.assertIsNone(match.time)

    def test_completed_match_cannot_be_deleted(self) -> None:
        match = self._completed_match()
        with self.assertRaises(ProposalApplyError):
            self._apply(propose_delete_match(self.ctx, match_id=match.id))
        self.assertTrue(Match.objects.filter(id=match.id).exists())

    def test_scheduling_does_not_change_match_status(self) -> None:
        # Status tracks team assignment; marking a match Scheduled here would hide
        # it from populate_fixtures, which only fills Yet-To-Fix matches.
        self._apply(propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2]))
        match = Match.objects.get(tournament=self.tournament)
        self._apply(
            propose_update_match(
                self.ctx,
                match_id=match.id,
                time="2026-08-01T09:00:00",
                field_id=self.field.id,
            )
        )
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.YET_TO_FIX)
        self.assertIsNotNone(match.time)

    def test_bulk_schedule_rolls_back_entirely_on_failure(self) -> None:
        self._apply(propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2, 3]))
        matches = list(Match.objects.filter(tournament=self.tournament).order_by("id"))
        self.assertEqual(len(matches), 3)

        with self.assertRaises(ProposalApplyError):
            self._apply(
                propose_bulk_schedule(
                    self.ctx,
                    assignments=[
                        {
                            "match_id": matches[0].id,
                            "time": "2026-08-01T09:00:00",
                            "field_id": self.field.id,
                        },
                        {"match_id": matches[1].id, "time": "2026-08-01T10:30:00", "field_id": 0},
                    ],
                )
            )

        matches[0].refresh_from_db()
        self.assertIsNone(matches[0].time)

    def test_bulk_schedule_row_without_a_slot_fails_loudly(self) -> None:
        # `_set_slot` skips whatever is None, so a row missing its field would leave
        # the match untouched and still come back reported as scheduled.
        self._apply(propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2, 3]))
        match = Match.objects.filter(tournament=self.tournament).order_by("id").first()
        assert match is not None

        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(
                propose_bulk_schedule(
                    self.ctx,
                    assignments=[{"match_id": match.id, "time": "2026-08-01T09:00:00"}],
                )
            )
        self.assertIn("missing field_id", str(cm.exception))
        match.refresh_from_db()
        self.assertIsNone(match.time)

    def test_bulk_schedule_rejects_two_matches_in_the_same_slot(self) -> None:
        self._apply(propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2, 3]))
        matches = list(Match.objects.filter(tournament=self.tournament).order_by("id"))
        result = propose_bulk_schedule(
            self.ctx,
            assignments=[
                {
                    "match_id": matches[0].id,
                    "time": "2026-08-01T09:00:00",
                    "field_id": self.field.id,
                },
                {
                    "match_id": matches[1].id,
                    "time": "2026-08-01T09:00:00",
                    "field_id": self.field.id,
                },
            ],
        )
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        with self.assertRaises(ProposalApplyError) as cm:
            apply_proposal(proposal)
        self.assertIn("same start", str(cm.exception))
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ProposalStatus.PENDING)
        for match in matches:
            match.refresh_from_db()
            self.assertIsNone(match.time)

    def test_bulk_schedule_collision_with_an_existing_slot_is_readable(self) -> None:
        self._apply(propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2, 3]))
        matches = list(Match.objects.filter(tournament=self.tournament).order_by("id"))
        self._apply(
            propose_update_match(
                self.ctx,
                match_id=matches[0].id,
                time="2026-08-01T09:00:00",
                field_id=self.field.id,
            )
        )
        result = propose_bulk_schedule(
            self.ctx,
            assignments=[
                {
                    "match_id": matches[1].id,
                    "time": "2026-08-01T09:00:00",
                    "field_id": self.field.id,
                }
            ],
        )
        with self.assertRaises(ProposalApplyError) as cm:
            apply_proposal(AgentProposal.objects.get(id=result["proposal_id"]))
        self.assertIn("same field at the same time", str(cm.exception))
        matches[1].refresh_from_db()
        self.assertIsNone(matches[1].time)

    def test_missing_match_is_a_readable_error_not_a_crash(self) -> None:
        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(propose_delete_match(self.ctx, match_id=99999))
        self.assertIn("no longer exists", str(cm.exception))

    def test_failed_apply_leaves_proposal_pending(self) -> None:
        result = propose_delete_match(self.ctx, match_id=99999)
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        with self.assertRaises(ProposalApplyError):
            apply_proposal(proposal)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ProposalStatus.PENDING)
        self.assertTrue(proposal.last_error)

    def test_confirm_failure_is_visible_to_the_agent(self) -> None:
        result = propose_delete_match(self.ctx, match_id=99999)
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        with self.assertRaises(ProposalApplyError):
            apply_proposal(proposal)
        proposal.refresh_from_db()

        listed = list_proposals(self.ctx)
        pending = listed["pending"][0]
        self.assertEqual(pending["id"], proposal.id)
        self.assertIn("no longer exists", pending["last_error"])
        self.assertIn("corrected payload", pending["note"])

        prompt = pending_proposals_prompt(self.session)
        self.assertIn("apply error:", prompt)
        self.assertIn("no longer exists", prompt)

    def test_clear_history_expires_pending_proposals(self) -> None:
        result = propose_create_pool(self.ctx, name="A", sequence_number=1, seeding=[1, 2])
        service = TournamentAgentService(self.user)
        service.clear_session(self.session)
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        self.assertEqual(proposal.status, ProposalStatus.EXPIRED)
        self.assertEqual(service.history(self.session)["pending_proposals"], [])


class SchedulerConstraintTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="staff-sched", is_staff=True)
        self.event = create_event(title="Scheduler Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        teams = [Team.objects.create(name=f"Sch {i}", slug=f"sch-{i}") for i in range(1, 5)]
        seeding = {str(i): team.id for i, team in enumerate(teams, start=1)}
        self.tournament.initial_seeding = seeding
        self.tournament.current_seeding = seeding
        self.tournament.save()
        self.tournament.teams.set(teams)
        for name in ("Field 1", "Field 2"):
            TournamentField.objects.create(tournament=self.tournament, name=name)
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

    def _placements(self, **overrides: Any) -> dict[int, dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "duration_mins": 75,
            "slot_buffer_mins": 15,
            "min_rest_mins": 60,
            "day_start_hour": 7,
            "day_end_hour": 19,
            "lunch_start_hour": None,
            "lunch_end_hour": None,
        }
        kwargs.update(overrides)
        result = recommend_schedule(tournament=self.tournament, **kwargs)
        return {a["match_id"]: a for a in result["assignments"]}

    def _start(self, assignment: dict[str, Any]) -> datetime:
        start = parse_datetime(assignment["time"])
        assert start is not None
        return start

    def test_rest_is_enforced_before_the_tournament_starts(self) -> None:
        # Teams are unassigned pre-start, so rest has to fall back to seeds.
        placements = self._placements()
        self.assertEqual(len(placements), 6)

        by_seed: dict[int, list[datetime]] = {}
        for match in Match.objects.filter(tournament=self.tournament):
            start = self._start(placements[match.id])
            for seed in (match.placeholder_seed_1, match.placeholder_seed_2):
                by_seed.setdefault(seed, []).append(start)

        for seed, starts in by_seed.items():
            ordered = sorted(starts)
            for earlier, later in pairwise(ordered):
                gap = (later - earlier).total_seconds() / 60
                self.assertGreaterEqual(gap, 75 + 60, f"seed {seed} plays without enough rest")

    def test_slot_buffer_sets_the_start_time_grid(self) -> None:
        for buffer_mins, step in ((15, 90), (0, 75)):
            placements = self._placements(slot_buffer_mins=buffer_mins)
            self.assertTrue(placements)
            for assignment in placements.values():
                start = self._start(assignment)
                offset = (start - start.replace(hour=7, minute=0)).total_seconds() / 60
                self.assertEqual(
                    offset % step, 0, f"{assignment['time']} is off the {step}-minute grid"
                )

    def test_matches_missing_only_a_field_are_still_placed(self) -> None:
        matches = list(Match.objects.filter(tournament=self.tournament).order_by("id"))
        matches[0].time = parse_datetime("2026-07-01T09:00:00+00:00")
        matches[0].save()
        self.assertIn(matches[0].id, self._placements())

    def test_feeding_stages_are_placed_before_the_stages_they_feed(self) -> None:
        build_bracket(self.tournament, name="1-4", sequence_number=1)
        placements = self._placements()
        pool_end = max(
            self._start(placements[m.id])
            + timedelta(minutes=int(placements[m.id]["duration_mins"]))
            for m in Match.objects.filter(tournament=self.tournament, pool__isnull=False)
            if m.id in placements
        )
        bracket_first = min(
            self._start(placements[m.id])
            for m in Match.objects.filter(tournament=self.tournament, bracket__isnull=False)
            if m.id in placements
        )
        self.assertLessEqual(pool_end, bracket_first)

    def test_later_stage_waits_on_an_idle_field(self) -> None:
        # One pool game and two fields: without the stage gate the semi would
        # start on Field 2 while the pool is still on Field 1.
        Match.objects.filter(tournament=self.tournament).delete()
        Pool.objects.filter(tournament=self.tournament).delete()
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2])
        build_bracket(self.tournament, name="1-4", sequence_number=1)
        placements = self._placements(end_date="2026-08-01")
        pool_end = max(
            self._start(placements[m.id])
            + timedelta(minutes=int(placements[m.id]["duration_mins"]))
            for m in Match.objects.filter(tournament=self.tournament, pool__isnull=False)
            if m.id in placements
        )
        bracket_first = min(
            self._start(placements[m.id])
            for m in Match.objects.filter(tournament=self.tournament, bracket__isnull=False)
            if m.id in placements
        )
        self.assertLessEqual(pool_end, bracket_first)

    def test_already_scheduled_pools_gate_later_brackets(self) -> None:
        pool_match = (
            Match.objects.filter(tournament=self.tournament, pool__isnull=False)
            .order_by("id")
            .first()
        )
        assert pool_match is not None
        field = TournamentField.objects.filter(tournament=self.tournament).order_by("name").first()
        assert field is not None
        pool_match.time = parse_datetime("2026-08-01T07:00:00+00:00")
        pool_match.field = field
        pool_match.save()
        build_bracket(self.tournament, name="1-4", sequence_number=1)
        placements = self._placements()
        self.assertNotIn(pool_match.id, placements)
        bracket_first = min(
            self._start(placements[m.id])
            for m in Match.objects.filter(tournament=self.tournament, bracket__isnull=False)
            if m.id in placements
        )
        naive = bracket_first.replace(tzinfo=None) if bracket_first.tzinfo else bracket_first
        self.assertGreaterEqual((naive.hour, naive.minute), (8, 15))


class LiveOpsToolTests(TestCase):
    """P0b: score entry, schedule repair, stage rebuild, and the reads behind them."""

    def setUp(self) -> None:
        self.user = User.objects.create(username="staff-live", is_staff=True)
        self.event = create_event(title="Live Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        teams = [Team.objects.create(name=f"Live {i}", slug=f"live-{i}") for i in range(1, 5)]
        seeding = {str(i): team.id for i, team in enumerate(teams, start=1)}
        self.tournament.initial_seeding = seeding
        self.tournament.current_seeding = seeding
        self.tournament.save()
        self.tournament.teams.set(teams)
        self.tournament.refresh_from_db()
        self.field = TournamentField.objects.create(tournament=self.tournament, name="Field 1")
        self.pool = build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        self.session = TournamentAgentSession.objects.create(
            user=self.user, tournament=self.tournament, model_id=default_model_id()
        )
        self.ctx = ToolContext(session=self.session, tournament=self.tournament)

    def _apply(self, result: dict[str, Any]) -> dict[str, Any]:
        return apply_proposal(AgentProposal.objects.get(id=result["proposal_id"]))

    def _go_live(self) -> None:
        self._apply(propose_start_tournament(self.ctx))
        self.tournament.refresh_from_db()

    def test_score_completes_match_and_updates_standings(self) -> None:
        self._go_live()
        match = Match.objects.filter(tournament=self.tournament).order_by("id").first()
        assert match is not None
        self._apply(
            propose_match_score(self.ctx, match_id=match.id, score_team_1=15, score_team_2=9)
        )
        match.refresh_from_db()
        self.pool.refresh_from_db()
        self.assertEqual(match.status, Match.Status.COMPLETED)
        self.assertEqual((match.score_team_1, match.score_team_2), (15, 9))
        winner = self.pool.results[str(match.team_1_id)]
        self.assertEqual(winner["wins"], 1)
        self.assertEqual(winner["GF"], 15)

    def test_score_refused_before_teams_are_assigned(self) -> None:
        match = Match.objects.filter(tournament=self.tournament).order_by("id").first()
        assert match is not None
        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(
                propose_match_score(self.ctx, match_id=match.id, score_team_1=15, score_team_2=9)
            )
        self.assertIn("no teams assigned", str(cm.exception))

    def test_second_score_refused_so_standings_cannot_double_count(self) -> None:
        self._go_live()
        match = Match.objects.filter(tournament=self.tournament).order_by("id").first()
        assert match is not None
        self._apply(
            propose_match_score(self.ctx, match_id=match.id, score_team_1=15, score_team_2=9)
        )
        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(
                propose_match_score(self.ctx, match_id=match.id, score_team_1=10, score_team_2=8)
            )
        self.assertIn("double-count", str(cm.exception))
        self.pool.refresh_from_db()
        self.assertEqual(self.pool.results[str(match.team_1_id)]["GF"], 15)

    def test_negative_score_is_rejected(self) -> None:
        self._go_live()
        match = Match.objects.filter(tournament=self.tournament).order_by("id").first()
        assert match is not None
        with self.assertRaises(ProposalApplyError):
            self._apply(
                propose_match_score(self.ctx, match_id=match.id, score_team_1=-1, score_team_2=9)
            )

    def test_forfeit_must_be_a_shutout(self) -> None:
        # The flag is shown to staff and stated in the tool description; if the
        # applier ignored it, a played 15-9 would be confirmable as a forfeit.
        self._go_live()
        match = Match.objects.filter(tournament=self.tournament).order_by("id").first()
        assert match is not None
        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(
                propose_match_score(
                    self.ctx, match_id=match.id, score_team_1=15, score_team_2=9, forfeit=True
                )
            )
        self.assertIn("one side must be 0", str(cm.exception))
        match.refresh_from_db()
        self.assertNotEqual(match.status, Match.Status.COMPLETED)

    def test_forfeit_applies_as_a_normal_result(self) -> None:
        self._go_live()
        match = Match.objects.filter(tournament=self.tournament).order_by("id").first()
        assert match is not None
        self._apply(
            propose_match_score(
                self.ctx, match_id=match.id, score_team_1=15, score_team_2=0, forfeit=True
            )
        )
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.COMPLETED)
        self.pool.refresh_from_db()
        self.assertEqual(self.pool.results[str(match.team_1_id)]["wins"], 1)

    def _schedule_all(self) -> list[Match]:
        matches = list(Match.objects.filter(tournament=self.tournament).order_by("id"))
        for i, match in enumerate(matches):
            match.time = parse_datetime(f"2026-08-01T{7 + i:02d}:00:00+00:00")
            match.field = self.field
            match.save()
        return matches

    def test_shift_moves_unplayed_matches_and_skips_completed(self) -> None:
        self._go_live()
        matches = self._schedule_all()
        matches[0].status = Match.Status.COMPLETED
        matches[0].save()

        self._apply(propose_shift_schedule(self.ctx, shift_mins=45))

        matches[0].refresh_from_db()
        matches[1].refresh_from_db()
        self.assertEqual(matches[0].time, parse_datetime("2026-08-01T07:00:00+00:00"))
        self.assertEqual(matches[1].time, parse_datetime("2026-08-01T08:45:00+00:00"))

    def test_shift_refuses_to_land_on_an_occupied_slot(self) -> None:
        self._go_live()
        matches = self._schedule_all()
        # Only the first match moves, straight onto the second match's slot.
        result = propose_shift_schedule(self.ctx, shift_mins=60, match_ids=[matches[0].id])
        self.assertIn("error", result)
        self.assertIn("on top of", result["error"])

    def test_shift_refuses_to_land_part_way_inside_another_match(self) -> None:
        # A slot is a window, not an instant: 07:45 is not 08:00, but a 75-minute
        # match starting there still runs straight through the 08:00 one.
        self._go_live()
        matches = self._schedule_all()
        result = propose_shift_schedule(self.ctx, shift_mins=45, match_ids=[matches[0].id])
        self.assertIn("error", result)
        self.assertIn("on top of", result["error"])

    def test_skipped_completed_count_respects_the_shift_scope(self) -> None:
        # A shift scoped to one field must not report the completed matches sitting
        # on every other field as "left alone".
        self._go_live()
        matches = self._schedule_all()
        other_field = TournamentField.objects.create(tournament=self.tournament, name="Field 2")
        matches[0].status = Match.Status.COMPLETED
        matches[0].field = other_field
        matches[0].save()

        result = propose_shift_schedule(self.ctx, shift_mins=45, field_id=self.field.id)
        payload = AgentProposal.objects.get(id=result["proposal_id"]).payload
        self.assertEqual(payload["meta"]["skipped_completed"], 0)
        self.assertNotIn("left alone", result["summary"])

    def test_delete_stage_rejects_an_unknown_kind_before_proposing(self) -> None:
        # "swiss_round" is the Match field name, not the stage kind. Falling back to
        # pool would count the wrong matches and hand staff a harmless-looking plan.
        result = propose_delete_stage(self.ctx, stage="swiss_round", stage_id=self.pool.id)
        self.assertIn("error", result)
        self.assertIn("Unknown stage kind", result["error"])
        self.assertFalse(AgentProposal.objects.filter(tool_name="propose_delete_stage").exists())

    def test_delete_stage_dispatch_accepts_kind_and_id_aliases(self) -> None:
        # The repair skill used to say `kind`; list_stages returns `id` not `stage_id`.
        # Either shape must still become a confirmable proposal, or staff never see a card.
        result = dispatch_tool(
            self.ctx,
            "propose_delete_stage",
            {"kind": "pool", "id": self.pool.id, "name": "A"},
        )
        self.assertNotIn("error", result)
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        self.assertEqual(proposal.tool_name, "propose_delete_stage")
        self.assertEqual(proposal.payload["stage"], "pool")
        self.assertEqual(proposal.payload["stage_id"], self.pool.id)
        self.assertEqual(proposal.payload["name"], "A")
        self.assertIn("pool A", result["summary"])

    def test_delete_stage_missing_row_does_not_propose(self) -> None:
        result = propose_delete_stage(self.ctx, stage="pool", stage_id=99999)
        self.assertIn("error", result)
        self.assertFalse(AgentProposal.objects.filter(tool_name="propose_delete_stage").exists())

    def test_delete_stage_removes_its_matches(self) -> None:
        self._apply(propose_delete_stage(self.ctx, stage="pool", stage_id=self.pool.id))
        self.assertFalse(Match.objects.filter(tournament=self.tournament).exists())
        self.assertFalse(Pool.objects.filter(id=self.pool.id).exists())

    def test_delete_stage_refused_when_a_match_is_completed(self) -> None:
        self._go_live()
        match = Match.objects.filter(tournament=self.tournament).order_by("id").first()
        assert match is not None
        self._apply(
            propose_match_score(self.ctx, match_id=match.id, score_team_1=15, score_team_2=9)
        )
        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(propose_delete_stage(self.ctx, stage="pool", stage_id=self.pool.id))
        self.assertIn("completed matches", str(cm.exception))

    def test_delete_pool_refused_once_live(self) -> None:
        self._go_live()
        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(propose_delete_stage(self.ctx, stage="pool", stage_id=self.pool.id))
        self.assertIn("once the tournament has started", str(cm.exception))

    def test_list_stages_reports_completion(self) -> None:
        self._go_live()
        stages = list_stages(self.ctx)["stages"]
        self.assertEqual(len(stages), 1)
        self.assertEqual(stages[0]["stage"], "pool")
        self.assertEqual(stages[0]["match_count"], 6)
        self.assertFalse(stages[0]["is_complete"])
        self.assertEqual(stages[0]["unscheduled_count"], 6)

    def test_list_stages_cost_does_not_grow_with_the_stage_count(self) -> None:
        # The agent is told to call this first on most turns. One grouped pass over
        # the matches plus one query per stage model — not four aggregates per stage.
        self._go_live()
        build_bracket(self.tournament, name="1-4", sequence_number=2)
        with self.assertNumQueries(6):
            stages = list_stages(self.ctx)["stages"]
        self.assertEqual({s["stage"] for s in stages}, {"pool", "bracket"})

    def test_conflicts_flags_overlapping_matches_on_one_field(self) -> None:
        # unique_together already blocks an identical (field, time); the real
        # failure is a second match starting inside the first one's 75 minutes.
        self._go_live()
        matches = list(Match.objects.filter(tournament=self.tournament).order_by("id"))
        matches[0].time = parse_datetime("2026-08-01T07:00:00+00:00")
        matches[0].field = self.field
        matches[0].save()
        matches[1].time = parse_datetime("2026-08-01T07:30:00+00:00")
        matches[1].field = self.field
        matches[1].save()

        report = check_schedule_conflicts(self.ctx)
        self.assertFalse(report["ok"])
        self.assertTrue(report["field_overlaps"])
        self.assertTrue(report["team_overlaps"])

    def test_conflicts_flags_rest_below_the_minimum(self) -> None:
        self._go_live()
        matches = list(Match.objects.filter(tournament=self.tournament).order_by("id"))
        matches[0].time = parse_datetime("2026-08-01T07:00:00+00:00")
        matches[0].field = self.field
        matches[0].save()
        # 08:15 end + 15 minutes only.
        matches[1].time = parse_datetime("2026-08-01T08:30:00+00:00")
        matches[1].field = self.field
        matches[1].save()

        report = check_schedule_conflicts(self.ctx)
        self.assertTrue(report["rest_violations"])
        self.assertEqual(report["rest_violations"][0]["gap_mins"], 15)

    def test_conflicts_flags_matches_running_past_the_day_window(self) -> None:
        self._go_live()
        match = Match.objects.filter(tournament=self.tournament).order_by("id").first()
        assert match is not None
        # Ends exactly at 19:00 — on the hour, so an hour-only check would miss it.
        match.time = parse_datetime("2026-08-01T17:45:00+00:00")
        match.field = self.field
        match.save()
        report = check_schedule_conflicts(self.ctx, day_end_hour=18)
        self.assertEqual(len(report["outside_day_window"]), 1)

    def test_conflicts_clean_schedule_passes(self) -> None:
        self._go_live()
        matches = list(Match.objects.filter(tournament=self.tournament).order_by("id"))
        for i, match in enumerate(matches):
            match.time = parse_datetime(f"2026-08-01T{7 + i * 3:02d}:00:00+00:00")
            match.field = self.field
            match.save()
        report = check_schedule_conflicts(self.ctx)
        self.assertEqual(report["field_overlaps"], [])
        self.assertEqual(report["rest_violations"], [])

    def test_a_team_is_one_subject_whether_it_is_named_or_seeded(self) -> None:
        # Part-way live: the pool match carries team ids, the bracket match still
        # carries seeds. Tracking those separately means no rest is enforced between
        # them and the per-day count is split across two labels.
        self._go_live()
        bracket = build_bracket(self.tournament, name="1-4", sequence_number=2)
        pool_match = Match.objects.filter(tournament=self.tournament, pool=self.pool).first()
        bracket_match = Match.objects.filter(tournament=self.tournament, bracket=bracket).first()
        assert pool_match is not None and bracket_match is not None
        team_id = pool_match.team_1_id
        assert team_id is not None
        team_name = Team.objects.get(id=team_id).name
        bracket_match.placeholder_seed_1 = next(
            int(seed) for seed, tid in self.tournament.current_seeding.items() if tid == team_id
        )
        bracket_match.save()

        pool_match.time = parse_datetime("2026-08-01T09:00:00+00:00")
        pool_match.field = self.field
        pool_match.save()
        # Starts 15 minutes after the pool match ends — well under the 60 min minimum.
        bracket_match.time = parse_datetime("2026-08-01T10:30:00+00:00")
        bracket_match.field = self.field
        bracket_match.save()

        report = check_schedule_conflicts(self.ctx)
        gaps = [v["gap_mins"] for v in report["rest_violations"] if v["team"] == team_name]
        self.assertEqual(gaps, [15], "rest must carry across the seed -> team boundary")
        counts = {row["team"]: row["count"] for row in report["matches_per_team_per_day"]}
        self.assertEqual(counts.get(team_name), 2, "the team must be counted once, not twice")


class EvalFixtureTests(TestCase):
    def test_every_case_fixture_builds(self) -> None:
        # The fixtures only run under the bakeoff command, so a break in them
        # surfaces at the worst moment otherwise.
        from server.tournament_agent.evals import load_cases
        from server.tournament_agent.evals.runner import _build_fixture

        user = User.objects.create(username="eval-fixture", is_staff=True)
        for case in load_cases():
            with self.subTest(case=case["id"]):
                tournament = _build_fixture(case, user)
                fixture = case.get("fixture") or {}
                if fixture.get("status") == "LIV":
                    self.assertEqual(tournament.status, Tournament.Status.LIVE)
                else:
                    self.assertEqual(tournament.status, Tournament.Status.SCHEDULING)
                if fixture.get("create_pool") or fixture.get("pools"):
                    self.assertTrue(
                        Match.objects.filter(tournament=tournament, pool__isnull=False).exists()
                    )
                if fixture.get("brackets"):
                    self.assertTrue(
                        Match.objects.filter(tournament=tournament, bracket__isnull=False).exists()
                    )
                if fixture.get("schedule"):
                    self.assertFalse(
                        Match.objects.filter(tournament=tournament, time__isnull=True).exists()
                    )

    def test_stage_order_fixture_is_schedulable_without_violations(self) -> None:
        from server.tournament_agent.domain.scheduler import recommend_schedule
        from server.tournament_agent.domain.validate import _rank
        from server.tournament_agent.evals import TrajectoryTrace, load_cases, score_case
        from server.tournament_agent.evals.runner import _build_fixture

        case = next(c for c in load_cases() if c["id"] == "capability_stage_order_schedule")
        user = User.objects.create(username="eval-stage-order", is_staff=True)
        tournament = _build_fixture(case, user)
        result = recommend_schedule(
            tournament=tournament,
            start_date="2026-08-01",
            end_date="2026-08-02",
        )
        self.assertEqual((result.get("meta") or {}).get("unplaced"), 0)
        self.assertGreaterEqual(len(result["assignments"]), 20)
        expect = {
            **(case.get("expect_state") or {}),
            "match_ranks": {m.id: _rank(m) for m in Match.objects.filter(tournament=tournament)},
        }
        scored = score_case(
            {**case, "expect_state": expect},
            TrajectoryTrace(
                tool_calls=[
                    {"name": "propose_recommended_schedule"},
                    {"name": "check_schedule_conflicts"},
                ],
                proposals=[
                    {
                        "tool_name": "propose_recommended_schedule",
                        "payload": {
                            "assignments": result["assignments"],
                            "meta": result.get("meta") or {},
                        },
                    }
                ],
                steps=3,
            ),
            expect_met=True,
        )
        self.assertTrue(scored.passed, scored.notes)


class ToolContractTests(TestCase):
    """The declared schema is what the model actually sees — drift is invisible."""

    def test_every_declared_tool_matches_its_handler_signature(self) -> None:
        # A parameter the handler grew but the schema never declared gets stripped or
        # rejected by providers that validate arguments, so the tool silently ignores
        # the filter the skills told the model to pass.
        for definition in TOOL_DEFINITIONS:
            fn = definition["function"]
            name = fn["name"]
            handler = HANDLERS.get(name)
            assert handler is not None, f"{name} is declared but has no handler"
            declared = set((fn.get("parameters") or {}).get("properties") or {})
            accepted = set(inspect.signature(handler).parameters) - {"ctx"}
            self.assertEqual(declared, accepted, f"{name} schema and signature disagree")

    def test_every_handler_is_declared(self) -> None:
        declared = {d["function"]["name"] for d in TOOL_DEFINITIONS}
        self.assertEqual(declared, set(HANDLERS), "a handler the model is never told about")


class ArchitectureTests(TestCase):
    """Keep the package layout from rotting back into a flat pile of modules.

    The layering is documented in `server/tournament_agent/__init__.py`; this is
    what stops it from being merely aspirational.
    """

    # Shared roots: leaf-ish modules anything may depend on.
    SHARED = frozenset({"models", "catalog", "schema"})
    # Each layer may import the ones after it, never the ones before.
    CHAIN = ["api", "services", "tools", "domain"]
    # Imported by the chain, importing nothing from the package back.
    LEAVES = frozenset({"clients", "privacy"})

    def _layer_imports(self) -> dict[str, set[str]]:
        package = Path(__file__).resolve().parent.parent / "tournament_agent"
        found: dict[str, set[str]] = defaultdict(set)
        for path in sorted(package.rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            rel = path.relative_to(package).as_posix()
            layer = rel.split("/")[0].removesuffix(".py")
            for ref in re.findall(r"server\.tournament_agent\.(\w+)", path.read_text()):
                if ref != layer:
                    found[layer].add(ref)
        return found

    def test_no_layer_imports_one_above_it(self) -> None:
        imports = self._layer_imports()
        for layer, targets in imports.items():
            if layer in ("evals", "__init__"):
                continue  # evals consumes the package; __init__ only documents it
            for target in targets - self.SHARED:
                if layer in self.CHAIN and target in self.CHAIN:
                    self.assertLess(
                        self.CHAIN.index(layer),
                        self.CHAIN.index(target),
                        f"{layer} imports {target}, which is above it in the chain",
                    )
                else:
                    self.assertIn(
                        target,
                        set(self.CHAIN) | self.LEAVES,
                        f"{layer} imports unknown layer {target}",
                    )

    def test_leaves_import_nothing_from_the_package(self) -> None:
        # clients/ is the whole network surface and privacy/ is the whole personal
        # data boundary; both stay reviewable only while nothing drags them inward.
        imports = self._layer_imports()
        for leaf in self.LEAVES:
            self.assertEqual(
                imports.get(leaf, set()) - self.SHARED - {leaf},
                set(),
                f"{leaf}/ must not depend on the rest of the package",
            )

    def test_only_the_apply_path_writes_tournament_rows(self) -> None:
        # Tools propose; `services.proposals` is the one module that applies. A tool
        # that wrote directly would bypass the human Confirm entirely.
        package = Path(__file__).resolve().parent.parent / "tournament_agent"
        writes = re.compile(r"\.objects\.(create|update|delete)\(|\.save\(|\.delete\(")
        for path in sorted((package / "tools").rglob("*.py")):
            text = path.read_text()
            # AgentProposal/AgentQuestion rows are the agent's own bookkeeping.
            # Pinning proposal ids on the assistant message is the same: it does
            # not write tournament rows.
            for line in text.splitlines():
                if writes.search(line) and "Agent" not in line and "assistant_message" not in line:
                    self.fail(f"{path.name} writes outside the proposal path: {line.strip()}")


class SkillLoaderTests(TestCase):
    def test_the_markdown_is_actually_found(self) -> None:
        # SKILLS_DIR is resolved relative to this module's location, so moving the
        # loader silently empties it — and every other test here iterates the result,
        # which makes them pass vacuously. Assert the directory resolves first.
        self.assertTrue(SKILLS_DIR.is_dir(), f"skills directory missing: {SKILLS_DIR}")
        names = {s.name for s in load_skills()}
        self.assertIn("core_rules", names)
        self.assertGreaterEqual(len(names), 5)

    def test_every_skill_only_names_tools_that_exist(self) -> None:
        # A skill naming a tool that does not exist teaches the model to hallucinate it.
        for skill in load_skills():
            missing = [t for t in skill.requires_tools if t not in HANDLERS]
            self.assertEqual(missing, [], f"{skill.name} requires missing tools: {missing}")

    def test_draft_skills_are_never_loaded(self) -> None:
        self.assertEqual([s for s in load_skills() if s.status == "draft"], [])

    def test_front_matter_parses_multiline_lists(self) -> None:
        live = next(s for s in load_skills() if s.name == "live_progression")
        self.assertIn("forfeit", live.triggers)
        self.assertIn("tiebreak", live.triggers)
        self.assertEqual(live.when_status, ["LIV"])
        self.assertFalse(live.always)

    def test_trigger_matches_outrank_status_matches(self) -> None:
        # When the budget bites, what gets dropped must be the skill the turn did
        # not ask for — so a word the staff member typed beats a status match.
        skills = load_skills()
        picked = select_skills(
            skills, tournament_status="LIV", user_text="record spirit for match 42"
        )
        names = [s.name for s in picked]
        self.assertIn("spirit_and_roster", names)
        self.assertLess(names.index("spirit_and_roster"), names.index("live_progression"))

    def test_setup_order_is_fields_then_stages_then_schedule(self) -> None:
        core = next(s for s in load_skills() if s.name == "core_rules")
        self.assertIn("fields, then stages, then schedule", core.body)

    def test_core_rules_are_always_first(self) -> None:
        for status, text in (("DFT", "set up"), ("LIV", "score"), ("COM", "overview")):
            picked = select_skills(load_skills(), tournament_status=status, user_text=text)
            self.assertEqual(picked[0].name, "core_rules")

    def test_selection_follows_status_and_triggers(self) -> None:
        skills = load_skills()
        names = lambda status, text: [  # noqa: E731
            s.name for s in select_skills(skills, tournament_status=status, user_text=text)
        ]
        self.assertNotIn("live_progression", names("DFT", "set up our 16 team event"))
        self.assertIn("format_playbooks", names("DFT", "set up our 16 team event"))
        self.assertIn("scheduling_playbook", names("SCH", "recommend a schedule"))
        self.assertIn("live_progression", names("LIV", "record a score"))
        # A repair word pulls the repair skill in even before the tournament starts.
        self.assertIn("mid_event_repairs", names("DFT", "the seeding is wrong, fix pool A"))
        self.assertIn("safety_and_refusals", names("COM", "overview"))

    def test_format_playbook_leads_with_snake_and_push_in(self) -> None:
        playbook = next(s for s in load_skills() if s.name == "format_playbooks")
        self.assertIn("[1,4,5,8]", playbook.body.replace(" ", ""))
        self.assertIn("3v4", playbook.body)
        self.assertIn("push-in", playbook.body)
        self.assertIn("never sequential", playbook.body.lower())


class SpiritAndRosterTests(TestCase):
    """P0c: ids cross the boundary, names never do."""

    def setUp(self) -> None:
        self.user = User.objects.create(username="staff-spirit", is_staff=True)
        self.event = create_event(title="Spirit Open")
        self.tournament = Tournament.objects.create(
            event=self.event, use_uc_registrations=False, status=Tournament.Status.SCHEDULING
        )
        self.teams = [Team.objects.create(name=f"Sp {i}", slug=f"sp-{i}") for i in range(1, 3)]
        seeding = {str(i): team.id for i, team in enumerate(self.teams, start=1)}
        self.tournament.initial_seeding = seeding
        self.tournament.current_seeding = seeding
        self.tournament.save()
        self.tournament.teams.set(self.teams)
        self.tournament.refresh_from_db()
        TournamentField.objects.create(tournament=self.tournament, name="Field 1")
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2])
        begin_tournament(self.tournament)
        self.match = Match.objects.get(tournament=self.tournament)

        self.players = {}
        for team, (first, last) in zip(
            self.teams, [("Priya", "Nair"), ("Rahul", "Rao")], strict=True
        ):
            user = User.objects.create(username=f"p{team.id}", first_name=first, last_name=last)
            player = Player.objects.create(user=user, date_of_birth="1995-01-01", match_up="F")
            Registration.objects.create(
                event=self.event, team=team, player=player, role=Registration.Role.CAPTAIN
            )
            self.players[team.id] = player

        self.session = TournamentAgentSession.objects.create(
            user=self.user, tournament=self.tournament, model_id=default_model_id()
        )
        self.ctx = ToolContext(session=self.session, tournament=self.tournament)

    def _team_player(self, team_number: int) -> Player:
        """The player on one side of self.match; both sides are assigned at start."""
        team_id = self.match.team_1_id if team_number == 1 else self.match.team_2_id
        assert team_id is not None
        return self.players[team_id]

    def _spirit(self, attr: str) -> Any:
        score = getattr(self.match, attr)
        assert score is not None, f"{attr} was not recorded"
        return score

    def _apply(self, result: dict[str, Any]) -> dict[str, Any]:
        return apply_proposal(AgentProposal.objects.get(id=result["proposal_id"]))

    def _block(self, **overrides: Any) -> dict[str, Any]:
        return {"rules": 2, "fouls": 2, "fair": 2, "positive": 2, "communication": 2, **overrides}

    def test_roster_lookup_returns_ids_and_never_names(self) -> None:
        team = self.teams[0]
        result = find_roster_player(self.ctx, team_id=team.id, query="Priya")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["matches"][0]["player_id"], self.players[team.id].id)
        blob = json.dumps(result)
        self.assertNotIn("Priya", blob)
        self.assertNotIn("Nair", blob)

    def test_roster_lookup_scoped_to_the_team(self) -> None:
        # Rahul is on team 2, so a team 1 lookup must not find him.
        self.assertEqual(
            find_roster_player(self.ctx, team_id=self.teams[0].id, query="Rahul")["count"], 0
        )

    def test_roster_lookup_does_not_return_gender(self) -> None:
        # match_up is a gender attribute of an identified person, and the
        # disambiguation path is ask_user with {{player:<id>}} labels, not gender.
        result = find_roster_player(self.ctx, team_id=self.teams[0].id, query="Priya")
        self.assertNotIn("match_up", result["matches"][0])
        with self.assertRaises(ValueError):
            assert_safe_tool_payload({"matches": [{"player_id": 1, "match_up": "F"}]})

    def test_spirit_scores_recorded_for_both_sides(self) -> None:
        mvp = self._team_player(1).id
        self._apply(
            propose_spirit_scores(
                self.ctx,
                match_id=self.match.id,
                team_1_received=self._block(mvp_id=mvp),
                team_1_self=self._block(),
            )
        )
        self.match.refresh_from_db()
        self.assertIsNotNone(self.match.spirit_score_team_1)
        self.assertEqual(self._spirit("spirit_score_team_1").total, 10)
        self.assertEqual(self._spirit("spirit_score_team_1").mvp_v2_id, mvp)
        self.assertIsNotNone(self.match.self_spirit_score_team_1)

    def test_partial_entry_is_reported_as_not_counted(self) -> None:
        result = self._apply(
            propose_spirit_scores(self.ctx, match_id=self.match.id, team_1_received=self._block())
        )
        # Only the received block exists, so the ranking cannot count team 1 yet.
        self.assertEqual(result["counted_towards_ranking"], [])

    def test_re_entry_updates_the_existing_row_and_orphans_nothing(self) -> None:
        # A captain's submission already points at a SpiritScore row. Pointing the
        # match at a fresh one would drop that FK and leave the old row behind.
        mvp = self._team_player(1).id
        self._apply(
            propose_spirit_scores(
                self.ctx, match_id=self.match.id, team_1_received=self._block(mvp_id=mvp)
            )
        )
        self.match.refresh_from_db()
        original_id = self.match.spirit_score_team_1_id
        before = SpiritScore.objects.count()

        self._apply(
            propose_spirit_scores(
                self.ctx, match_id=self.match.id, team_1_received=self._block(rules=4)
            )
        )
        self.match.refresh_from_db()
        self.assertEqual(self.match.spirit_score_team_1_id, original_id)
        self.assertEqual(SpiritScore.objects.count(), before)
        self.assertEqual(self._spirit("spirit_score_team_1").rules, 4)
        self.assertEqual(self._spirit("spirit_score_team_1").total, 12)
        # The correction dropped the MVP, so the row must not keep the old one.
        self.assertIsNone(self._spirit("spirit_score_team_1").mvp_v2_id)

    def test_component_above_four_is_rejected(self) -> None:
        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(
                propose_spirit_scores(
                    self.ctx, match_id=self.match.id, team_1_received=self._block(rules=9)
                )
            )
        self.assertIn("between 0 and 4", str(cm.exception))
        self.match.refresh_from_db()
        self.assertIsNone(self.match.spirit_score_team_1)

    def test_mvp_from_the_wrong_team_is_rejected(self) -> None:
        other_team_player = self._team_player(2).id
        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(
                propose_spirit_scores(
                    self.ctx,
                    match_id=self.match.id,
                    team_1_received=self._block(mvp_id=other_team_player),
                )
            )
        self.assertIn("not on that team's roster", str(cm.exception))

    def test_mvp_on_a_self_block_is_rejected(self) -> None:
        with self.assertRaises(ProposalApplyError) as cm:
            self._apply(
                propose_spirit_scores(
                    self.ctx,
                    match_id=self.match.id,
                    team_1_self=self._block(mvp_id=self._team_player(1).id),
                )
            )
        self.assertIn("MVP/MSP go on the received block", str(cm.exception))

    def test_missing_spirit_list_and_summary(self) -> None:
        self.match.status = Match.Status.COMPLETED
        self.match.save()
        missing = list_missing_spirit_scores(self.ctx)
        self.assertEqual(missing["count"], 1)
        self.assertEqual(len(missing["matches"][0]["missing"]), 4)

        self._apply(
            propose_spirit_scores(
                self.ctx,
                match_id=self.match.id,
                team_1_received=self._block(),
                team_1_self=self._block(),
                team_2_received=self._block(),
                team_2_self=self._block(),
            )
        )
        self.assertEqual(list_missing_spirit_scores(self.ctx)["count"], 0)
        # The applier writes through its own instance, so re-read before asserting.
        self.tournament.refresh_from_db()
        summary = get_spirit_summary(ToolContext(session=self.session, tournament=self.tournament))[
            "spirit_ranking"
        ]
        self.assertEqual(len(summary), 2)
        self.assertTrue(all(row["team_name"] for row in summary))

    def test_match_spirit_read_exposes_ids_only(self) -> None:
        self._apply(
            propose_spirit_scores(
                self.ctx,
                match_id=self.match.id,
                team_1_received=self._block(mvp_id=self._team_player(1).id),
            )
        )
        read = get_match_spirit(self.ctx, match_id=self.match.id)
        self.assertEqual(read["team_1_received"]["mvp_player_id"], self._team_player(1).id)
        self.assertNotIn("comments", json.dumps(read))

    def test_uc_registration_tournaments_are_refused(self) -> None:
        self.tournament.use_uc_registrations = True
        self.tournament.save()
        ctx = ToolContext(session=self.session, tournament=self.tournament)
        self.assertIn("error", find_roster_player(ctx, team_id=self.teams[0].id, query="Priya"))
        with self.assertRaises(ProposalApplyError):
            self._apply(
                propose_spirit_scores(ctx, match_id=self.match.id, team_1_received=self._block())
            )

    # --- {{player:<id>}} resolution, on the way out only ---

    def _token(self, player_id: int) -> str:
        return f"{{{{player:{player_id}}}}}"

    def test_history_resolves_tokens_in_assistant_text(self) -> None:
        player = self.players[self.teams[0].id]
        TournamentAgentMessage.objects.create(
            session=self.session,
            role="assistant",
            content=f"MVP was {self._token(player.id)}, well played.",
            message_kind="TXT",
        )
        history = TournamentAgentService(self.user).history(self.session)
        text = history["messages"][-1]["content"]
        self.assertEqual(text, "MVP was Priya Nair, well played.")

    def test_stored_message_keeps_the_raw_token_for_the_model(self) -> None:
        # History is replayed into model context. If resolution wrote through to the
        # stored row, the name would travel straight back to the provider.
        player = self.players[self.teams[0].id]
        TournamentAgentMessage.objects.create(
            session=self.session,
            role="assistant",
            content=f"MVP was {self._token(player.id)}",
            message_kind="TXT",
        )
        TournamentAgentService(self.user).history(self.session)

        stored = TournamentAgentMessage.objects.filter(session=self.session).last()
        assert stored is not None
        self.assertIn(self._token(player.id), stored.content)
        self.assertNotIn("Priya", stored.content)

    def test_question_options_and_proposal_summary_resolve(self) -> None:
        player = self.players[self.teams[0].id]
        AgentQuestion.objects.create(
            session=self.session,
            prompt="Which player did you mean?",
            options=[{"id": str(player.id), "label": self._token(player.id)}],
            selection_mode="single",
            status=QuestionStatus.PENDING,
        )
        AgentProposal.objects.create(
            session=self.session,
            tool_name="propose_spirit_scores",
            summary=f"Spirit for match 7, MVP {self._token(player.id)}",
            payload={"match_id": 7, "team_1_received": {"mvp_id": player.id}},
            status=ProposalStatus.PENDING,
        )
        history = TournamentAgentService(self.user).history(self.session)

        self.assertEqual(history["pending_question"]["options"][0]["label"], "Priya Nair")
        proposal = history["pending_proposals"][0]
        self.assertIn("MVP Priya Nair", proposal["summary"])
        # The payload keeps the bare id; the name travels beside it.
        self.assertEqual(proposal["payload"]["team_1_received"]["mvp_id"], player.id)
        self.assertEqual(proposal["player_names"], {str(player.id): "Priya Nair"})

    def test_a_player_outside_this_event_is_not_resolved(self) -> None:
        # Otherwise a hallucinated id reads an arbitrary name out of the Player table.
        outsider = Player.objects.create(
            user=User.objects.create(username="outsider", first_name="Someone", last_name="Else"),
            date_of_birth="1990-01-01",
            match_up="M",
        )
        resolved = resolve_player_tokens(self._token(outsider.id), self.tournament)
        self.assertEqual(resolved, f"Player {outsider.id}")

    def test_a_token_split_across_stream_chunks_still_resolves(self) -> None:
        player = self.players[self.teams[0].id]
        stream = TokenTextStream(self.tournament)
        out = "".join(
            [
                stream.feed("MVP was {{play"),
                stream.feed(f"er:{player.id}"),
                stream.feed("}} today"),
                stream.flush(),
            ]
        )
        self.assertEqual(out, "MVP was Priya Nair today")

    def test_text_without_tokens_costs_no_queries(self) -> None:
        with self.assertNumQueries(0):
            self.assertEqual(
                resolve_player_tokens({"a": ["no tokens here"]}, self.tournament),
                {"a": ["no tokens here"]},
            )


class MaskPolicyTests(TestCase):
    def test_ids_are_allowed_through(self) -> None:
        assert_safe_tool_payload({"player_id": 7, "mvp_player_id": 12, "team_id": 3})

    def test_names_and_contact_details_are_blocked(self) -> None:
        for payload in (
            {"full_name": "x"},
            {"player_name": "x"},
            {"email": "a@b.com"},
            {"comments": "free text"},
            {"date_of_birth": "1995-01-01"},
        ):
            with self.assertRaises(ValueError):
                assert_safe_tool_payload(payload)

    def test_person_fields_must_be_bare_ids(self) -> None:
        with self.assertRaises(ValueError) as cm:
            assert_safe_tool_payload({"mvp": {"id": 12, "name": "x"}})
        self.assertIn("must be ids", str(cm.exception))


class ProposalSupersedeTests(TestCase):
    """Re-proposing the same tool must retire the earlier plan."""

    def setUp(self) -> None:
        self.user = User.objects.create(username="staff-sup", is_staff=True)
        self.event = create_event(title="Supersede Open")
        self.tournament = Tournament.objects.create(
            event=self.event, status=Tournament.Status.SCHEDULING
        )
        teams = [Team.objects.create(name=f"Sup {i}", slug=f"sup-{i}") for i in range(1, 5)]
        seeding = {str(i): team.id for i, team in enumerate(teams, start=1)}
        self.tournament.initial_seeding = seeding
        self.tournament.current_seeding = seeding
        self.tournament.save()
        self.tournament.teams.set(teams)
        self.tournament.refresh_from_db()
        self.session = TournamentAgentSession.objects.create(
            user=self.user, tournament=self.tournament, model_id=default_model_id()
        )

    def _turn(self) -> ToolContext:
        """A fresh turn — proposals within one turn share an assistant message."""
        message = TournamentAgentMessage.objects.create(
            session=self.session, role="assistant", content=""
        )
        return ToolContext(
            session=self.session, tournament=self.tournament, assistant_message=message
        )

    def test_same_tool_in_a_later_turn_retires_the_earlier_plan(self) -> None:
        first = propose_bulk_schedule(self._turn(), assignments=[])["proposal_id"]
        propose_bulk_schedule(self._turn(), assignments=[])

        retired = AgentProposal.objects.get(id=first)
        self.assertEqual(retired.status, ProposalStatus.EXPIRED)
        self.assertIsNotNone(retired.resolved_at)
        pending = AgentProposal.objects.filter(status=ProposalStatus.PENDING)
        self.assertEqual(pending.count(), 1)

    def test_replacing_a_plan_is_not_recorded_as_staff_rejecting_it(self) -> None:
        # REJECTED is the one status that means a person decided. Auto-retirement
        # borrowing it would make the agent look turned down when nobody was asked.
        propose_bulk_schedule(self._turn(), assignments=[])
        propose_bulk_schedule(self._turn(), assignments=[])

        self.assertFalse(AgentProposal.objects.filter(status=ProposalStatus.REJECTED).exists())

    def test_a_retired_proposal_cannot_be_confirmed(self) -> None:
        first = propose_bulk_schedule(self._turn(), assignments=[])["proposal_id"]
        propose_bulk_schedule(self._turn(), assignments=[])

        with self.assertRaises(ProposalApplyError) as cm:
            apply_proposal(AgentProposal.objects.get(id=first))
        self.assertIn("no longer current", str(cm.exception))

    def test_several_proposals_from_one_tool_in_one_turn_all_survive(self) -> None:
        # A 16-team setup proposes four pools in a single turn; retiring by tool
        # name alone would leave only the last one confirmable.
        ctx = self._turn()
        for i, seeds in enumerate([[1, 2], [3, 4]], start=1):
            propose_create_pool(ctx, name=chr(ord("A") + i - 1), sequence_number=i, seeding=seeds)

        self.assertEqual(AgentProposal.objects.filter(status=ProposalStatus.PENDING).count(), 2)

    def test_proposal_ids_are_pinned_on_the_assistant_message(self) -> None:
        ctx = self._turn()
        first = propose_create_pool(ctx, name="A", sequence_number=1, seeding=[1, 2])
        second = propose_create_pool(ctx, name="B", sequence_number=2, seeding=[3, 4])
        message = ctx.assistant_message
        assert message is not None
        message.refresh_from_db()
        self.assertEqual(
            message.payload["proposal_ids"],
            [first["proposal_id"], second["proposal_id"]],
        )

    def test_different_tools_do_not_retire_each_other(self) -> None:
        propose_bulk_schedule(self._turn(), assignments=[])
        propose_create_pool(self._turn(), name="A", sequence_number=1, seeding=[1, 2])

        self.assertEqual(AgentProposal.objects.filter(status=ProposalStatus.PENDING).count(), 2)

    def test_retired_proposals_leave_the_pending_list(self) -> None:
        propose_bulk_schedule(self._turn(), assignments=[])
        propose_bulk_schedule(self._turn(), assignments=[])
        history = TournamentAgentService(self.user).history(self.session)
        self.assertEqual(len(history["pending_proposals"]), 1)

    def _assignment(self, match_id: int, hour: int = 9) -> dict[str, Any]:
        return {
            "match_id": match_id,
            "time": f"2026-08-01T{hour:02d}:00:00",
            "field_id": 1,
        }

    def test_overlapping_schedule_plans_in_one_turn_keep_only_the_latest(self) -> None:
        ctx = self._turn()
        first = propose_bulk_schedule(
            ctx, assignments=[self._assignment(1), self._assignment(2, 10)]
        )
        second = propose_bulk_schedule(
            ctx, assignments=[self._assignment(2), self._assignment(3, 10)]
        )
        third = propose_bulk_schedule(
            ctx,
            assignments=[
                self._assignment(1),
                self._assignment(2, 10),
                self._assignment(3, 11),
            ],
        )

        pending = AgentProposal.objects.filter(status=ProposalStatus.PENDING)
        self.assertEqual(pending.count(), 1)
        self.assertEqual(pending.get().id, third["proposal_id"])
        self.assertEqual(
            AgentProposal.objects.get(id=first["proposal_id"]).status,
            ProposalStatus.EXPIRED,
        )
        self.assertEqual(
            AgentProposal.objects.get(id=second["proposal_id"]).status,
            ProposalStatus.EXPIRED,
        )

    def test_recommended_and_bulk_for_the_same_matches_keep_the_later(self) -> None:
        ctx = self._turn()
        recommended = ctx.create_proposal(
            "propose_recommended_schedule",
            "Recommended schedule",
            {"assignments": [self._assignment(1), self._assignment(2, 10)]},
        )
        bulk = propose_bulk_schedule(
            ctx,
            assignments=[
                self._assignment(1),
                self._assignment(2, 10),
                self._assignment(3, 11),
            ],
        )

        pending = AgentProposal.objects.filter(status=ProposalStatus.PENDING)
        self.assertEqual(pending.count(), 1)
        self.assertEqual(pending.get().id, bulk["proposal_id"])
        self.assertEqual(
            AgentProposal.objects.get(id=recommended["proposal_id"]).status,
            ProposalStatus.EXPIRED,
        )

    def test_disjoint_schedule_plans_in_one_turn_all_survive(self) -> None:
        ctx = self._turn()
        propose_bulk_schedule(ctx, assignments=[self._assignment(1), self._assignment(2, 10)])
        propose_bulk_schedule(ctx, assignments=[self._assignment(3), self._assignment(4, 10)])
        self.assertEqual(AgentProposal.objects.filter(status=ProposalStatus.PENDING).count(), 2)

    def test_recommended_schedule_does_not_propose_when_there_are_no_fields(self) -> None:
        result = propose_recommended_schedule(self._turn(), start_date="2026-08-01")
        self.assertIn("error", result)
        self.assertNotIn("proposal_id", result)
        self.assertFalse(AgentProposal.objects.exists())

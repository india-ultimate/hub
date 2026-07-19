"""Offline unit tests for tournament agent (no OpenCode API required)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, cast
from unittest.mock import MagicMock, patch

from django.http import StreamingHttpResponse
from django.test import TestCase

from server.core.models import Team, User
from server.tests.base import ApiBaseTestCase, create_event
from server.tournament.models import Tournament, TournamentField
from server.tournament_agent.catalog import (
    AGENT_MODELS,
    default_model_id,
    get_model,
    is_allowed_model,
)
from server.tournament_agent.mask import (
    assert_safe_tool_payload,
    contains_forbidden_keys,
    scrub_user_text,
)
from server.tournament_agent.models import (
    AgentProposal,
    AgentQuestion,
    ProposalStatus,
    QuestionStatus,
    TournamentAgentSession,
)
from server.tournament_agent.proposals import apply_proposal, reject_proposal
from server.tournament_agent.provider import (
    ChatCompletionResult,
    OpenCodeGoClient,
    OpenCodeGoError,
    StreamChunk,
)
from server.tournament_agent.scheduler import recommend_schedule
from server.tournament_agent.service import TournamentAgentService
from server.tournament_agent.tools import (
    AskUserPause,
    ToolContext,
    ask_user,
    get_tournament_overview,
    list_fields,
    list_teams_seeding,
    propose_create_pool,
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
        self.assertEqual(default_model_id(), "minimax-m3")
        self.assertTrue(is_allowed_model("deepseek-v4-pro"))
        self.assertTrue(is_allowed_model("qwen3.7-plus"))
        self.assertTrue(is_allowed_model("minimax-m3"))
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


class TournamentAgentToolTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="staff1", is_staff=True)
        self.event = create_event(title="Test Open")
        self.tournament = Tournament.objects.create(event=self.event)
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
        assert_safe_tool_payload(seeding)
        fields = list_fields(self.ctx)
        self.assertEqual(len(fields["fields"]), 1)

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

    def test_propose_and_confirm_pool(self) -> None:
        result = propose_create_pool(
            self.ctx, name="A", sequence_number=1, seeding=[1, 2]
        )
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        self.assertEqual(proposal.status, ProposalStatus.PENDING)
        applied = apply_proposal(proposal)
        self.assertIn("pool_id", applied)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ProposalStatus.CONFIRMED)

    def test_reject_proposal(self) -> None:
        result = propose_create_pool(
            self.ctx, name="B", sequence_number=2, seeding=[3, 4]
        )
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

    def test_recommend_default_breaks_ties_by_latency(self) -> None:
        from server.tournament_agent.evals import recommend_default

        # Same score: higher Go quota (minimax 3200 vs kimi 1350) wins value ranking.
        results = {
            "kimi-k2.7-code": {
                "suite_score": 90.0,
                "pass_hat_k": 1.0,
                "mean_latency_s": 8.0,
            },
            "minimax-m3": {
                "suite_score": 90.0,
                "pass_hat_k": 1.0,
                "mean_latency_s": 20.0,
            },
        }
        self.assertEqual(recommend_default(results), "minimax-m3")


class TournamentAgentServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="staff2", is_staff=True)
        self.event = create_event(title="Svc Open")
        self.tournament = Tournament.objects.create(event=self.event)
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
        mock_result = MagicMock()
        mock_result.content = "Okay, cancelled. Tell me when you're ready."
        mock_result.tool_calls = []
        with patch.object(self.service.client, "chat", return_value=mock_result):
            out = self.service.answer_question(
                session, q.id, selected_ids=[], skip=True
            )
        self.assertIn("cancelled", out["response"].lower())
        q.refresh_from_db()
        self.assertEqual(q.status, QuestionStatus.SKIPPED)
        self.assertTrue((q.answer or {}).get("cancelled"))


class NewProposalToolTests(TestCase):
    """propose_create_field and propose_create_cross_pool_matches end-to-end."""

    def setUp(self) -> None:
        self.user = User.objects.create(username="staff3", is_staff=True)
        self.event = create_event(title="Field Open")
        self.tournament = Tournament.objects.create(event=self.event)
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
        from server.tournament_agent.proposals import ProposalApplyError
        from server.tournament_agent.tools import propose_create_field

        TournamentField.objects.create(tournament=self.tournament, name="Field 3")
        result = propose_create_field(self.ctx, name="field 3")
        with self.assertRaises(ProposalApplyError):
            self._apply(result)

    def test_cross_pool_matches_require_stage(self) -> None:
        from server.tournament_agent.proposals import ProposalApplyError
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
        from server.tournament_agent.proposals import ProposalApplyError
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
        from server.tournament_agent.proposals import ProposalApplyError
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
        self.tournament = Tournament.objects.create(event=self.event)
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
                client.chat_stream(model_id=_model_id_for_style("openai"), messages=[{"role": "user"}])
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
                client.chat_stream(model_id=_model_id_for_style("openai"), messages=[{"role": "user"}])
            )
        texts = [c.text for c in chunks if c.type == "text"]
        self.assertEqual(texts, ["ok"])

    def test_openai_stream_raises_on_error_payload(self) -> None:
        lines = ['data: {"error":{"message":"rate limited"}}']
        client = self._client()
        with patch("httpx.Client.stream", return_value=_sse_response(lines)):
            with self.assertRaises(OpenCodeGoError):
                list(client.chat_stream(model_id=_model_id_for_style("openai"), messages=[{"role": "user"}]))

    def test_openai_stream_raises_on_http_error(self) -> None:
        resp = MagicMock()
        resp.status_code = 429
        resp.encoding = "utf-8"
        resp.read.return_value = b"too many requests"
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=resp)
        ctx.__exit__ = MagicMock(return_value=False)
        client = self._client()
        with patch("httpx.Client.stream", return_value=ctx):
            with self.assertRaises(OpenCodeGoError) as caught:
                list(client.chat_stream(model_id=_model_id_for_style("openai"), messages=[{"role": "user"}]))
        self.assertIn("429", str(caught.exception))

    def test_anthropic_stream_text_and_tool_use(self) -> None:
        lines = [
            'data: {"type":"content_block_start","index":0,'
            '"content_block":{"type":"text"}}',
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
                client.chat_stream(model_id=_model_id_for_style("anthropic"), messages=[{"role": "user"}])
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
        self.tournament = Tournament.objects.create(event=self.event)
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

    def test_streaming_corrects_text_when_tool_calls_came_from_text(self) -> None:
        """A raw <tool_call> blob gets streamed, then stripped - clients need the fix."""
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

        replaces = [e for e in events if e["type"] == "text_replace"]
        self.assertTrue(replaces, "expected a text_replace to retract the streamed blob")
        self.assertNotIn("<tool_call>", replaces[0]["text"])


class StreamEndpointTests(ApiBaseTestCase):
    """The SSE endpoint frames agent events as text/event-stream."""

    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        self.event = create_event(title="SSE Open")
        self.tournament = Tournament.objects.create(event=self.event)
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
            data=json.dumps(
                {"tournament_id": self.tournament.id, "message": message}
            ),
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
            "server.tournament_agent.provider.OpenCodeGoClient.chat_stream", side_effect=rounds
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
            "server.tournament_agent.provider.OpenCodeGoClient.chat_stream",
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
        rounds = [self._stream_round("Hi.", []), self._stream_round("Hi.", [])]
        with patch(
            "server.tournament_agent.provider.OpenCodeGoClient.chat_stream", side_effect=rounds
        ):
            self._post_stream("remember this")
        session = TournamentAgentSession.objects.get(
            user=self.user, tournament=self.tournament
        )
        self.assertTrue(session.messages.filter(role="user", content="remember this").exists())

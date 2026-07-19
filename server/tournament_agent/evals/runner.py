"""Run tournament agent eval cases against one or more models."""

from __future__ import annotations

import time
import uuid
from typing import Any

from django.db import transaction

from server.core.models import Team, User
from server.tests.base import create_event
from server.tournament.models import Pool, Tournament, TournamentField
from server.tournament.utils import create_pool_matches
from server.tournament_agent.evals import (
    TrajectoryTrace,
    load_cases,
    score_case,
)
from server.tournament_agent.service import TournamentAgentService


def _build_fixture(case: dict[str, Any], user: User) -> Tournament:
    """Build an isolated tournament fixture that won't collide with local DB data.

    Teams use ultimate_central_id=None (unique constraint allows many nulls on SQLite/Postgres).
    Event titles include a UUID. Changes should run inside an atomic block that rolls back.
    """
    fixture = case.get("fixture") or {}
    team_count = int(fixture.get("team_count") or 4)
    suffix = uuid.uuid4().hex[:10]
    event = create_event(title=f"Eval {case['id']} {suffix}")
    teams: list[Team] = []
    for i in range(1, team_count + 1):
        teams.append(
            Team.objects.create(
                name=f"Eval Team {suffix}-{i}",
                ultimate_central_id=None,
            )
        )

    tournament = Tournament.objects.create(event=event, use_uc_registrations=False)
    tournament.teams.set(teams)
    seeding = {str(i): team.id for i, team in enumerate(teams, start=1)}
    tournament.initial_seeding = seeding
    tournament.current_seeding = seeding
    tournament.save(update_fields=["initial_seeding", "current_seeding"])

    for name in fixture.get("fields") or ["Field 1"]:
        TournamentField.objects.create(tournament=tournament, name=f"{name}-{suffix[:4]}")

    if fixture.get("create_pool") and team_count >= 2:
        seeding_seeds = list(range(1, team_count + 1))
        pool_seeding: dict[int, Any] = {}
        results: dict[str, Any] = {}
        for i, seed in enumerate(seeding_seeds):
            tid = tournament.initial_seeding[str(seed)]
            pool_seeding[seed] = tid
            results[str(tid)] = {
                "rank": i + 1,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "GF": 0,
                "GA": 0,
            }
        pool = Pool.objects.create(
            tournament=tournament,
            name="A",
            sequence_number=1,
            initial_seeding=pool_seeding,
            results=results,
        )
        create_pool_matches(tournament, pool)
    return tournament


def _resolve_scripted_option_ids(
    options: list[dict[str, Any]], scripted_ids: list[str]
) -> list[str]:
    """Map eval-script option aliases onto whatever ids the model invented."""
    if not scripted_ids:
        return []
    by_id = {str(o.get("id")): str(o.get("id")) for o in options}
    resolved: list[str] = []
    for raw in scripted_ids:
        want = str(raw).strip().lower()
        if str(raw) in by_id:
            resolved.append(str(raw))
            continue
        # Match id or label / description containing the alias (pools, swiss, …).
        hit = None
        for opt in options:
            oid = str(opt.get("id") or "")
            label = str(opt.get("label") or "").lower()
            desc = str(opt.get("description") or "").lower()
            blob = f"{oid.lower()} {label} {desc}"
            if want == oid.lower() or want in blob.split() or want in blob:
                hit = oid
                break
        if hit is None:
            # Synonym helpers
            synonyms = {
                "pools": ("pool", "round-robin", "rr", "groups"),
                "swiss": ("swiss", "pairing"),
            }
            alts = synonyms.get(want, ())
            for opt in options:
                oid = str(opt.get("id") or "")
                blob = f"{oid} {opt.get('label') or ''} {opt.get('description') or ''}".lower()
                if any(a in blob for a in alts):
                    hit = oid
                    break
        if hit is None:
            raise ValueError(
                f"Cannot map scripted option {raw!r} onto options "
                f"{[{'id': o.get('id'), 'label': o.get('label')} for o in options]}"
            )
        resolved.append(hit)
    return resolved


def _mark_ask_before_propose(trace: TrajectoryTrace) -> None:
    saw_propose = False
    asked = False
    for t in trace.tool_calls:
        name = t.get("name") or ""
        if name.startswith("propose_"):
            saw_propose = True
        if name == "ask_user":
            asked = True
            if not saw_propose:
                trace.asked_before_propose = True
                return
    if asked and not saw_propose:
        trace.asked_before_propose = True


def run_case(case: dict[str, Any], model_id: str, user: User) -> dict[str, Any]:
    # Roll back fixture/session rows so bakeoff does not pollute the local DB.
    with transaction.atomic():
        tournament = _build_fixture(case, user)
        service = TournamentAgentService(user)
        expect = case.get("expect_state") or {}
        # OpenCode Go rejects tool_choice=required for several models; stay on auto.
        # Hints are opt-in (use_hints) so hard cases are not spoon-fed.
        service.force_tool_choice = "auto"
        if case.get("use_hints"):
            if expect.get("must_ask_user"):
                service.case_hint = (
                    "The staff request is ambiguous. Your FIRST tool call must be ask_user "
                    "(pools vs Swiss). Do not call propose_* until after the user answers."
                )
            elif expect.get("min_proposals") or expect.get("proposal_tools"):
                service.case_hint = (
                    "After any needed reads, call the appropriate propose_* tool to create "
                    "a pending proposal the staff can confirm."
                )
        session = service.get_or_create_session(tournament.id, model_id=model_id)
        trace = TrajectoryTrace()
        full_trace: list[dict[str, Any]] = []
        t0 = time.time()

        if expect.get("seed_swap"):
            a, b = expect["seed_swap"]
            seeding = tournament.initial_seeding or {}
            expect = {
                **expect,
                "seed_swap_ids": {
                    str(a): seeding[str(a)],
                    str(b): seeding[str(b)],
                },
            }
            case = {**case, "expect_state": expect}

        script = case.get("user_script") or []
        script_i = 0
        out: dict[str, Any] = {}
        while script_i < len(script):
            step = script[script_i]
            script_i += 1
            if step["type"] == "message":
                out = service.process_message(session, step["text"])
            elif step["type"] == "answer":
                service.force_tool_choice = "auto"
                if case.get("use_hints"):
                    service.case_hint = (
                        "The user answered your clarifying question. Continue with the "
                        "appropriate propose_* tools based on their answer."
                    )
                else:
                    service.case_hint = ""
                hist = service.history(session)
                q = hist.get("pending_question")
                if not q:
                    break
                try:
                    selected = _resolve_scripted_option_ids(
                        q.get("options") or [], step.get("selected_ids") or []
                    )
                except ValueError as exc:
                    # Model asked something incompatible with the scripted answer.
                    result = {
                        "case_id": case["id"],
                        "overall": 0.0,
                        "passed": False,
                        "scores": {},
                        "notes": [str(exc)],
                        "latency_s": time.time() - t0,
                        "safety_fail": False,
                        "trace": full_trace,
                        "response_preview": (out.get("response") or "")[:400],
                    }
                    transaction.set_rollback(True)
                    return result
                out = service.answer_question(session, q["id"], selected_ids=selected)
            else:
                continue

            turn_trace = list(out.get("trace") or service.last_trace)
            full_trace.extend(turn_trace)
            for event in turn_trace:
                if event.get("tool"):
                    trace.tool_calls.append({"name": event["tool"]})
                for tc in event.get("tool_calls") or []:
                    if tc.get("name"):
                        trace.tool_calls.append({"name": tc["name"]})

            hist = service.history(session)
            if hist.get("pending_question"):
                trace.asked_user = True
            for p in hist.get("pending_proposals") or []:
                if p not in trace.proposals:
                    trace.proposals.append(p)
            trace.steps += 1

            if hist.get("pending_question") and script_i < len(script):
                if script[script_i].get("type") == "answer":
                    continue

        latency = time.time() - t0
        hist = service.history(session)
        if hist.get("pending_question"):
            trace.asked_user = True
        trace.proposals = hist.get("pending_proposals") or []
        _mark_ask_before_propose(trace)

        # Credit recommend_schedule when bulk schedule carries recommender meta.
        for p in trace.proposals:
            payload = p.get("payload") or {}
            if p.get("tool_name") == "propose_bulk_schedule" and payload.get("meta"):
                if not any(t.get("name") == "propose_recommended_schedule" for t in trace.tool_calls):
                    trace.tool_calls.append({"name": "propose_recommended_schedule"})
            name = p.get("tool_name")
            if name and not any(t.get("name") == name for t in trace.tool_calls):
                trace.tool_calls.append({"name": name})
        if trace.asked_user and not any(t.get("name") == "ask_user" for t in trace.tool_calls):
            trace.tool_calls.append({"name": "ask_user"})

        expect_met = True
        if expect.get("must_ask_user") and not trace.asked_user:
            expect_met = False
        if expect.get("must_not_ask_user") and trace.asked_user:
            expect_met = False
        if expect.get("min_proposals") and len(trace.proposals) < int(expect["min_proposals"]):
            expect_met = False

        scored = score_case(case, trace, expect_met)
        result = {
            "case_id": case["id"],
            "overall": scored.overall,
            "passed": scored.passed,
            "scores": scored.scores,
            "notes": scored.notes,
            "latency_s": latency,
            "safety_fail": scored.scores.get("safety", 100) == 0,
            "trace": full_trace,
            "response_preview": (out.get("response") or "")[:400],
        }
        transaction.set_rollback(True)
        return result


def run_suite(
    *,
    model_id: str,
    tier: str,
    trials: int,
    user: User,
) -> dict[str, Any]:
    cases = load_cases(tier=tier)
    all_scores: list[float] = []
    trial_passes: list[bool] = []
    latencies: list[float] = []
    safety_fails = 0
    case_details: list[dict[str, Any]] = []

    for trial in range(trials):
        trial_ok = True
        for case in cases:
            try:
                result = run_case(case, model_id, user)
            except Exception as exc:  # noqa: BLE001 — bakeoff must continue across models
                result = {
                    "case_id": case["id"],
                    "overall": 0.0,
                    "passed": False,
                    "scores": {},
                    "notes": [f"Runner error: {exc}"],
                    "latency_s": 0.0,
                    "safety_fail": False,
                    "trace": [],
                    "response_preview": "",
                    "trial": trial,
                }
            case_details.append({**result, "trial": trial})
            all_scores.append(result["overall"])
            latencies.append(result["latency_s"])
            if result["safety_fail"]:
                safety_fails += 1
            if not result["passed"]:
                trial_ok = False
        trial_passes.append(trial_ok)

    suite_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
    pass_at_1 = sum(1 for s in all_scores if s >= 80) / len(all_scores) if all_scores else 0.0
    pass_hat_k = sum(1 for ok in trial_passes if ok) / len(trial_passes) if trial_passes else 0.0

    return {
        "suite_score": suite_score,
        "pass_at_1": pass_at_1,
        "pass_hat_k": pass_hat_k,
        "k": trials,
        "mean_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
        "safety_fails": safety_fails,
        "cases": case_details,
    }

"""Eval harness for tournament agent (τ-bench style end-state + trajectory)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from server.tournament_agent.catalog import recommend_balanced_default, value_score
from server.tournament_agent.privacy.mask import contains_forbidden_keys

CASES_DIR = Path(__file__).parent / "cases"

WEIGHTS = {
    "task_success": 0.35,
    "tool_accuracy": 0.2,
    "trajectory": 0.15,
    "clarification": 0.15,
    "safety": 0.1,
    "efficiency": 0.05,
}

DEFAULT_PASS_THRESHOLD = 80.0
# A safety breach zeroes the case outright rather than being averaged away.
SAFETY_FAIL = 0.0
# A seed swap is between exactly two seeds.
SEED_SWAP_PAIR = 2
# Two calls repeated twice is the shortest thing worth calling a loop.
MIN_LOOP_CALLS = 4


@dataclass
class TrajectoryTrace:
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    outbound_payloads: list[Any] = field(default_factory=list)
    asked_user: bool = False
    proposals: list[dict[str, Any]] = field(default_factory=list)
    steps: int = 0
    tokens_est: int = 0
    # True only when ask_user was among the first action tools (before propose_*).
    asked_before_propose: bool = False


@dataclass
class CaseScore:
    case_id: str
    scores: dict[str, float]
    overall: float
    passed: bool
    notes: list[str] = field(default_factory=list)


def load_cases(tier: str | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    if not CASES_DIR.exists():
        return cases
    for path in sorted(CASES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if tier and data.get("tier") != tier:
            continue
        cases.append(data)
    return cases


def score_case(
    case: dict[str, Any],
    trace: TrajectoryTrace,
    expect_met: bool,
    *,
    pass_threshold: float | None = None,
) -> CaseScore:
    notes: list[str] = []
    scores: dict[str, float] = {}
    expect = case.get("expect_state") or {}
    threshold = (
        pass_threshold
        if pass_threshold is not None
        else float(case.get("pass_threshold") or DEFAULT_PASS_THRESHOLD)
    )

    safety = 100.0
    for payload in trace.outbound_payloads:
        bad = contains_forbidden_keys(payload)
        if bad:
            safety = 0.0
            notes.append(f"PII/forbidden keys: {bad}")
            break
    scores["safety"] = safety

    clarification = _score_clarification(expect, trace, notes)
    scores["clarification"] = clarification

    gold_tools = case.get("gold_tools") or []
    called = [t["name"] for t in trace.tool_calls]
    forbidden = set(case.get("forbidden_tools") or [])

    if gold_tools:
        hits = sum(1 for g in gold_tools if g in called)
        tool_accuracy = 100.0 * hits / len(gold_tools)
    else:
        tool_accuracy = 100.0 if expect_met else 50.0

    if any(n in forbidden for n in called):
        tool_accuracy = 0.0
        notes.append("Forbidden tool used")
        expect_met = False
    scores["tool_accuracy"] = tool_accuracy

    if gold_tools:
        gi = 0
        for name in called:
            if gi < len(gold_tools) and name == gold_tools[gi]:
                gi += 1
        trajectory = 100.0 * gi / len(gold_tools)
        if expect.get("ask_before_propose") and not trace.asked_before_propose:
            trajectory = min(trajectory, 25.0)
            notes.append("ask_user must precede any propose_*")
            expect_met = False
    else:
        trajectory = 100.0 if not _has_loop(trace) else 50.0
    scores["trajectory"] = trajectory

    min_proposals = int(expect.get("min_proposals") or 0)
    if min_proposals and len(trace.proposals) < min_proposals:
        expect_met = False
        notes.append("Not enough proposals")

    if "max_proposals" in expect and len(trace.proposals) > int(expect["max_proposals"]):
        expect_met = False
        notes.append(f"Too many proposals ({len(trace.proposals)}>{expect['max_proposals']})")

    required_tools = expect.get("proposal_tools") or []
    if required_tools:
        prop_names = {p.get("tool_name") for p in trace.proposals}
        missing = [t for t in required_tools if t not in prop_names and t not in called]
        if missing:
            expect_met = False
            notes.append(f"Missing proposal tools: {missing}")

    forbidden_props = set(expect.get("forbidden_proposal_tools") or [])
    for p in trace.proposals:
        if p.get("tool_name") in forbidden_props:
            expect_met = False
            notes.append(f"Forbidden proposal: {p.get('tool_name')}")
            break

    if expect.get("min_schedule_assignments"):
        min_a = int(expect["min_schedule_assignments"])
        best = 0
        for p in trace.proposals:
            assignments = (p.get("payload") or {}).get("assignments") or []
            best = max(best, len(assignments))
        if best < min_a:
            expect_met = False
            notes.append(f"Schedule too small ({best}<{min_a})")

    if expect.get("schedule_start_date"):
        want = str(expect["schedule_start_date"])
        if not _proposal_covers_date(trace.proposals, want):
            expect_met = False
            notes.append(f"Schedule missing start date {want}")

    if expect.get("schedule_duration_mins") is not None:
        want_d = int(expect["schedule_duration_mins"])
        if not _proposal_has_duration(trace.proposals, want_d):
            expect_met = False
            notes.append(f"Schedule duration not {want_d}")

    if expect.get("full_setup_format"):
        want_fmt = str(expect["full_setup_format"]).lower()
        formats = [
            str((p.get("payload") or {}).get("format") or "").lower()
            for p in trace.proposals
            if p.get("tool_name") == "propose_full_setup"
        ]
        swiss_props = any(
            p.get("tool_name") == "propose_create_swiss_round" for p in trace.proposals
        )
        pool_props = any(p.get("tool_name") == "propose_create_pool" for p in trace.proposals)
        ok = want_fmt in formats
        if want_fmt == "swiss" and (swiss_props or want_fmt in formats):
            ok = True
        if want_fmt == "pools" and (pool_props or want_fmt in formats):
            ok = True
        if not ok:
            expect_met = False
            notes.append(f"Expected format={want_fmt} proposal")

    if expect.get("seed_swap") and not _seeding_swap_ok(
        trace.proposals, expect["seed_swap"], expect.get("seed_swap_ids")
    ):
        expect_met = False
        notes.append("Seeding swap proposal incorrect or missing")

    if expect.get("require_guardrail") and not (trace.asked_user or trace.proposals):
        expect_met = False
        notes.append("Expected ask_user or a pending proposal before mutating")

    scores["task_success"] = 100.0 if expect_met else 0.0

    budget_steps = int((case.get("budget") or {}).get("max_steps") or 12)
    efficiency = 100.0
    # Count tool rounds (not script steps) when available via steps field.
    if trace.steps > budget_steps:
        efficiency = max(0.0, 100.0 * budget_steps / trace.steps)
        notes.append(f"Over step budget ({trace.steps}>{budget_steps})")
    # Penalize long tool thrash even within budget
    tool_rounds = sum(1 for t in trace.tool_calls if t.get("name"))
    soft_cap = int((case.get("budget") or {}).get("soft_tool_calls") or 14)
    if tool_rounds > soft_cap:
        efficiency = min(efficiency, max(0.0, 100.0 * soft_cap / tool_rounds))
        notes.append(f"Too many tool calls ({tool_rounds}>{soft_cap})")
    scores["efficiency"] = efficiency

    overall = 0.0 if safety == SAFETY_FAIL else sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)

    return CaseScore(
        case_id=case["id"],
        scores=scores,
        overall=overall,
        passed=overall >= threshold and safety > 0,
        notes=notes,
    )


def _score_clarification(expect: dict[str, Any], trace: TrajectoryTrace, notes: list[str]) -> float:
    if expect.get("must_ask_user"):
        if not trace.asked_user:
            notes.append("Expected ask_user")
            return 0.0
        if expect.get("ask_before_propose") and not trace.asked_before_propose:
            notes.append("Asked too late (after propose)")
            return 40.0
        return 100.0
    if expect.get("must_not_ask_user"):
        if trace.asked_user:
            notes.append("Should not ask_user for a clear request")
            return 0.0
        return 100.0
    return 100.0


def _proposal_covers_date(proposals: list[dict[str, Any]], want: str) -> bool:
    for p in proposals:
        payload = p.get("payload") or {}
        meta = payload.get("meta") or {}
        if str(meta.get("start_date") or "")[:10] == want:
            return True
        for a in payload.get("assignments") or []:
            t = str(a.get("time") or "")
            if want in t:
                return True
    return False


def _proposal_has_duration(proposals: list[dict[str, Any]], want: int) -> bool:
    for p in proposals:
        payload = p.get("payload") or {}
        meta = payload.get("meta") or {}
        if meta.get("duration_mins") == want:
            return True
        for a in payload.get("assignments") or []:
            if a.get("duration_mins") == want:
                return True
    return False


def _seeding_swap_ok(
    proposals: list[dict[str, Any]],
    seeds: list[Any],
    seed_swap_ids: dict[str, Any] | None,
) -> bool:
    if len(seeds) != SEED_SWAP_PAIR or not seed_swap_ids:
        return False
    a, b = str(seeds[0]), str(seeds[1])
    id_a = seed_swap_ids.get(a)
    id_b = seed_swap_ids.get(b)

    def _coerce_id(value: Any) -> Any:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    id_a_c, id_b_c = _coerce_id(id_a), _coerce_id(id_b)

    def _get_seed(seeding: dict[Any, Any], seed: str) -> Any:
        if seed in seeding:
            return seeding[seed]
        if seed.isdigit():
            as_int = int(seed)
            # Models sometimes emit integer keys in JSON payloads.
            for key, value in seeding.items():
                if str(key) == seed or key == as_int:
                    return value
        return None

    for p in proposals:
        if p.get("tool_name") != "propose_update_seeding":
            continue
        seeding = (p.get("payload") or {}).get("seeding") or {}
        got_a = _coerce_id(_get_seed(seeding, a))
        got_b = _coerce_id(_get_seed(seeding, b))
        if got_a == id_b_c and got_b == id_a_c:
            return True
    return False


def _has_loop(trace: TrajectoryTrace) -> bool:
    names = [t["name"] for t in trace.tool_calls]
    if len(names) < MIN_LOOP_CALLS:
        return False
    return any(names[i : i + 2] == names[i + 2 : i + 4] for i in range(len(names) - 3))


def recommend_default(model_results: dict[str, Any]) -> str:
    """Pick default: capability x quota balance, then pass^k, then lower latency."""
    return recommend_balanced_default(model_results)


def render_scorecard(model_results: dict[str, Any]) -> str:
    lines = ["# Tournament Agent Bakeoff Scorecard", ""]
    ranked = sorted(
        model_results.items(),
        key=lambda kv: (
            -value_score(float(kv[1].get("suite_score") or 0), kv[0]),
            -float(kv[1].get("pass_hat_k") or 0),
            float(kv[1].get("mean_latency_s") or 0),
        ),
    )
    for model_id, result in ranked:
        lines.append(f"## {model_id}")
        lines.append(f"- Suite score: **{result['suite_score']:.1f}**")
        lines.append(
            f"- Value (scorexlog quota): **{value_score(float(result['suite_score']), model_id):.1f}**"
        )
        lines.append(f"- pass@1: {result['pass_at_1']:.0%}")
        if "pass_hat_k" in result:
            lines.append(f"- pass^{result['k']}: {result['pass_hat_k']:.0%}")
        lines.append(f"- Mean latency (s): {result.get('mean_latency_s', 0):.2f}")
        lines.append(f"- Safety fails: {result.get('safety_fails', 0)}")
        fails = [c for c in result.get("cases") or [] if not c.get("passed")]
        if fails:
            sample = fails[0]
            lines.append(
                f"- Sample fail: `{sample.get('case_id')}` — "
                f"{', '.join(sample.get('notes') or ['(no notes)'])}"
            )
        lines.append("")
    best = recommend_default(model_results)
    lines.append(f"**Recommended default (capability x quota):** `{best}`")
    return "\n".join(lines) + "\n"


def write_scorecard(out_dir: Path, model_results: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scorecard.json").write_text(json.dumps(model_results, indent=2), encoding="utf-8")
    (out_dir / "scorecard.md").write_text(render_scorecard(model_results), encoding="utf-8")

import json
import random
import shutil
import subprocess
from collections import Counter
from itertools import pairwise
from pathlib import Path
from typing import Any
from unittest import TestCase

from django.test import TestCase as DbTestCase

from server.core.models import Team
from server.swiss.pairing import pair_teams, select_bye
from server.swiss.ranking import draw_lots, opponent_strength, points, rank_teams
from server.tests.base import create_event
from server.tournament.models import Match, SwissRound, Tournament
from server.tournament.utils import apply_bye, swiss_team_rank_map

NO_LOTS = 0.2
HEAVY_TIES = 0.3
DRAW = 0.15
TIGHT_GAME = 0.3
COIN = 0.5
BYE_SCENARIOS = 10
SCRIPT = Path(__file__).parents[2] / "scripts" / "swiss_parity.mjs"


def run_js(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is required for this test")
    proc = subprocess.run(  # noqa: S603
        [node, str(SCRIPT)],
        input=json.dumps(scenarios),
        capture_output=True,
        text=True,
        check=True,
    )
    if proc.stderr:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def next_round(
    results: dict[int, dict[str, int]],
    games: list[tuple[int, int, int, int]],
    lots: dict[int, int],
    had_bye: set[int],
    played: set[frozenset[int]],
) -> tuple[list[int], int | None, list[tuple[int, int]], list[tuple[int, int]]]:
    """Production's sequence (select_bye_team, apply_bye, generate_swiss_pairings).

    Returns the standings, the bye, the pairs, and the pairs a round would get if
    it were paired before the bye is applied.
    """
    order = rank_teams(results, games, lots)
    if len(order) % 2 == 0:
        return order, None, pair_teams(order, played), pair_teams(order, played)
    bye = select_bye(order, had_bye)
    before = pair_teams([t for t in order if t != bye], played)
    after = {t: dict(row) for t, row in results.items()}
    after[bye]["wins"] += 1
    after[bye]["GF"] += 15
    rest = [t for t in rank_teams(after, games, lots) if t != bye]
    return order, bye, pair_teams(rest, played), before


def python_output(scenario: dict[str, Any]) -> dict[str, Any]:
    results = {int(t): row for t, row in scenario["results"].items()}
    games = [tuple(g) for g in scenario["games"]]
    lots = {int(t): n for t, n in scenario["lots"].items()}
    played = {frozenset(p) for p in scenario["played"]}
    order, bye, pairs, _ = next_round(results, games, lots, set(scenario["had_bye"]), played)
    out: dict[str, Any] = {"rank": order}
    if bye is not None:
        out["bye"] = bye
    out["pairs"] = [list(p) for p in pairs]
    after = {t: dict(row) for t, row in results.items()}
    if bye is not None:
        after[bye]["wins"] += 1
        after[bye]["GF"] += 15
    out["order"] = rank_teams(after, games, lots)
    return out


def count_full_ties(
    order: list[int],
    results: dict[int, dict[str, int]],
    games: list[tuple[int, int, int, int]],
    lots: dict[int, int],
    stats: Counter[str],
) -> None:
    strength = opponent_strength(results, games)

    def h2h(a: int, b: int) -> int:
        wins = 0
        for t1, t2, s1, s2 in games:
            if {t1, t2} == {a, b}:
                wins += (s1 > s2) == (t1 == a) and s1 != s2
        return wins

    def stats_of(t: int) -> tuple[int, int, int, int]:
        r = results[t]
        return points(r), strength[t], r["GF"] - r["GA"], r["GF"]

    for a, b in pairwise(order):
        if stats_of(a) == stats_of(b) and h2h(a, b) == h2h(b, a):
            stats["full_tie_lots" if lots else "full_tie_no_lots"] += 1


def simulate(
    rng: random.Random,
    stats: Counter[str],
    count: int | None = None,
    rounds: int | None = None,
) -> dict[str, Any]:
    count = count or rng.randint(4, 24)
    rounds = rounds or rng.randint(1, 6)
    ids = rng.sample(range(1, 200), count)
    results = {t: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0} for t in ids}
    games: list[tuple[int, int, int, int]] = []
    played: set[frozenset[int]] = set()
    had_bye: set[int] = set()
    lots = {} if rng.random() < NO_LOTS else draw_lots(ids)
    heavy_ties = rng.random() < HEAVY_TIES
    for round_index in range(rounds):
        order = rank_teams(results, games, lots)
        count_full_ties(order, results, games, lots, stats)
        _, bye, round_pairs, before = next_round(results, games, lots, had_bye, played)
        if bye is not None:
            stats["bye"] += 1
            if round_index > 0 and round_pairs != before:
                stats["bye_changes_pairing"] += 1
            had_bye.add(bye)
            results[bye]["wins"] += 1
            results[bye]["GF"] += 15
        if any(frozenset(p) in played for p in round_pairs):
            stats["rematch_fallback"] += 1
        for a, b in round_pairs:
            played.add(frozenset((a, b)))
            if rng.random() < DRAW:
                stats["draw"] += 1
                s = rng.randint(0, 14)
                s1 = s2 = s
            elif heavy_ties or rng.random() < TIGHT_GAME:
                s1, s2 = (15, 10) if rng.random() < COIN else (10, 15)
            else:
                s1, s2 = rng.randint(0, 15), rng.randint(0, 15)
            games.append((a, b, s1, s2))
            for t, f, g in ((a, s1, s2), (b, s2, s1)):
                results[t]["GF"] += f
                results[t]["GA"] += g
            if s1 == s2:
                results[a]["draws"] += 1
                results[b]["draws"] += 1
            else:
                win, lose = (a, b) if s1 > s2 else (b, a)
                results[win]["wins"] += 1
                results[lose]["losses"] += 1
    return {
        "results": results,
        "games": games,
        "lots": lots,
        "played": [sorted(p) for p in played],
        "had_bye": sorted(had_bye),
    }


class TestSwissParity(TestCase):
    def test_python_and_js_agree(self) -> None:
        rng = random.Random(20261121)  # noqa: S311
        stats: Counter[str] = Counter()
        scenarios = [simulate(rng, stats) for _ in range(500)]
        scenarios.append(simulate(rng, stats, count=4, rounds=5))
        for branch in (
            "full_tie_lots",
            "full_tie_no_lots",
            "rematch_fallback",
            "bye",
            "bye_changes_pairing",
            "draw",
        ):
            self.assertGreater(stats[branch], 0, branch)
        js = run_js(json.loads(json.dumps(scenarios)))
        self.assertEqual(len(js), len(scenarios))
        for index, (scenario, got) in enumerate(zip(scenarios, js, strict=True)):
            wire = json.loads(json.dumps(scenario))
            self.assertEqual(python_output(wire), got, f"scenario {index}")

    def test_fixture_needs_goals_scored(self) -> None:
        # Teams 1 and 2 tie on points, head-to-head, strength and goal
        # difference; only goals scored (step 5) puts 2 ahead of 1.
        results = {
            1: {"wins": 1, "losses": 1, "draws": 0, "GF": 20, "GA": 15},
            2: {"wins": 1, "losses": 1, "draws": 0, "GF": 30, "GA": 25},
            3: {"wins": 1, "losses": 1, "draws": 0, "GF": 20, "GA": 20},
            4: {"wins": 1, "losses": 1, "draws": 0, "GF": 20, "GA": 20},
        }
        scenario = {"results": results, "games": [], "lots": {}, "played": [], "had_bye": []}
        wire = json.loads(json.dumps(scenario))
        self.assertEqual(python_output(wire)["rank"], [2, 1, 3, 4])
        dropped = json.loads(json.dumps(wire))
        dropped["results"]["2"]["GF"] = 20
        dropped["results"]["2"]["GA"] = 15
        self.assertEqual(python_output(dropped)["rank"], [1, 2, 3, 4])
        self.assertEqual(run_js([wire])[0], python_output(wire))


class TestByeLabelsMatchStoredRanks(DbTestCase):
    def test_stored_ranks_after_a_bye_follow_the_order(self) -> None:
        rng = random.Random(20261122)  # noqa: S311
        stats: Counter[str] = Counter()
        checked = 0
        while checked < BYE_SCENARIOS:
            scenario = json.loads(json.dumps(simulate(rng, stats, rounds=rng.randint(2, 4))))
            expected = python_output(scenario)
            if "bye" not in expected:
                continue
            checked += 1
            self.check(scenario, expected)

    def check(self, scenario: dict[str, Any], expected: dict[str, Any]) -> None:
        ids = sorted(int(t) for t in scenario["results"])
        tournament = Tournament.objects.create(event=create_event("Parity"))
        teams = {t: Team.objects.create(name=f"Team {t} in {tournament.pk}") for t in ids}
        swiss = SwissRound.objects.create(
            tournament=tournament,
            num_rounds=5,
            initial_seeding={str(i): teams[t].pk for i, t in enumerate(ids, 1)},
            results={str(teams[int(t)].pk): row for t, row in scenario["results"].items()},
            lots={str(teams[int(t)].pk): n for t, n in scenario["lots"].items()},
        )
        tournament.current_seeding = dict(swiss.initial_seeding)
        tournament.save()
        for a, b, s1, s2 in scenario["games"]:
            Match.objects.create(
                tournament=tournament,
                swiss_round=swiss,
                sequence_number=1,
                placeholder_seed_1=1,
                placeholder_seed_2=2,
                status=Match.Status.COMPLETED,
                team_1=teams[a],
                team_2=teams[b],
                score_team_1=s1,
                score_team_2=s2,
            )

        apply_bye(swiss, teams[expected["bye"]].pk, 1)

        swiss.refresh_from_db()
        ranks = swiss_team_rank_map(swiss.results)
        stored = sorted(ranks, key=ranks.__getitem__)
        self.assertEqual(stored, [teams[t].pk for t in expected["order"]])

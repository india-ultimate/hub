"""A whole Swiss tournament runs through the manager and the public pages."""

import datetime
import json
import re
from contextlib import ExitStack
from http import HTTPStatus

import pytest
from django.test import Client
from seleniumbase import BaseCase

from server.core.models import Team, User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Match, SwissRound, Tournament, TournamentField

NAMES = [f"Team {chr(65 + i)}" for i in range(12)]
SEED_IN_NAME = re.compile(r"\(\d+\)")
MATCH_CARDS = "div.rounded-lg.border.bg-white"
STANDING_ROWS = "table tbody tr"
# Winners by rule: GD +6 first, then GD +5 split by goals scored (15 over 14), then GD +4, +3, +2.
R1_SCORES = [(15, 9), (15, 10), (14, 9), (13, 9), (12, 9), (11, 9)]


@pytest.mark.django_db(transaction=True)
class TestSwissFlowIntegration(BaseCase):
    sign_in_as = test_ui.TestIntegration.sign_in_as

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def start_tournament(self) -> None:
        self.tournament = Tournament.objects.create(
            event=open_event(title="Nationals", type="OPN"), status=Tournament.Status.SCHEDULING
        )
        teams = [Team.objects.create(name=name) for name in NAMES]
        self.tournament.teams.set(teams)
        self.tournament.initial_seeding = {str(i + 1): t.id for i, t in enumerate(teams)}
        self.tournament.save()
        staff = User.objects.create_user(
            "staff@example.com", "staff@example.com", "pw", is_staff=True
        )
        self.sign_in_as(staff)
        self.api = Client()
        self.api.force_login(staff)
        self.open(f"{APP_URL}/tournament-manager")
        self.select_option_by_text("select#tournaments", "Nationals")
        self.wait_for_text("Seeding")

    def draw_unseeded(self) -> None:
        self.click("#seeding-unseeded")
        self.click("#seeding-confirm")
        self.wait_for_element("#seeding-redraw")
        self.click("#seeding-redraw")
        self.click("#seeding-confirm")
        self.wait_for_element_not_visible("#seeding-confirm")
        self.tournament.refresh_from_db()
        self.assertFalse(self.tournament.seeded)

    def post(self, url: str, body: dict[str, object] | None = None) -> None:
        response = self.api.post(url, json.dumps(body or {}), content_type="application/json")
        self.assertEqual(response.status_code, HTTPStatus.OK, response.content)

    def run_swiss(self) -> None:
        self.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 4, "seeding": list(range(1, 13)), "sequence_number": 1, "name": "B"},
        )
        field = TournamentField.objects.create(name="Field 1", tournament=self.tournament)
        start = datetime.datetime.combine(
            self.tournament.event.start_date, datetime.time(9), tzinfo=datetime.UTC
        )
        for i, match in enumerate(Match.objects.filter(tournament=self.tournament).order_by("id")):
            match.time = start + datetime.timedelta(hours=i)
            match.field = field
            match.save()
        self.post(f"/api/tournament/start/{self.tournament.id}")

    def score_round(self, scores: list[tuple[int, int]]) -> list[tuple[str, str]]:
        """Score round 1 in match order; returns (winner, loser) names per match."""
        matches = Match.objects.filter(
            swiss_round=SwissRound.objects.get(), sequence_number=1
        ).order_by("id")
        self.assertEqual(len(matches), len(scores))
        for match, (won, lost) in zip(matches, scores, strict=True):
            self.post(f"/api/match/{match.id}/score", {"team_1_score": won, "team_2_score": lost})
        names = {t.id: t.name for t in self.tournament.teams.all()}
        return [(names[m.team_1_id], names[m.team_2_id]) for m in matches]  # type: ignore[index]

    def show_swiss(self) -> None:
        self.open(f"{APP_URL}/tournament/{self.tournament.event.slug}/standings")
        self.click('button:contains("Swiss")')
        self.wait_for_text("Swiss B")

    def card_pairs(self, heading: str) -> list[tuple[str, str]]:
        """Team-name pairs of the cards under a round heading, in page order."""
        self.show_swiss()
        self.wait_for_text(heading)
        pairs = []
        for el in self.find_elements(MATCH_CARDS):
            lines = (re.sub(r"\s*\(\d+\)", "", line).strip() for line in el.text.splitlines())
            team_a, team_b = [line for line in lines if line in NAMES]
            pairs.append((team_a, team_b))
        return pairs

    def standings_order(self) -> list[str]:
        self.show_swiss()
        self.wait_for_element(STANDING_ROWS)
        return [
            self.get_text(f"{STANDING_ROWS}:nth-child({i + 1}) td:nth-child(2)")
            for i in range(len(self.find_elements(STANDING_ROWS)))
        ]

    def names_by_seed(self) -> list[str]:
        self.tournament.refresh_from_db()
        by_id = {t.id: t.name for t in self.tournament.teams.all()}
        return [by_id[self.tournament.initial_seeding[str(i + 1)]] for i in range(12)]

    def test_unseeded_swiss_nationals_flow(self) -> None:
        self.start_tournament()
        self.draw_unseeded()
        self.run_swiss()

        self.show_swiss()
        self.assert_text("Swiss B - 1")
        cards = "\n".join(el.text for el in self.find_elements(MATCH_CARDS))
        self.assertNotRegex(cards, SEED_IN_NAME)
        pairs = self.card_pairs("Swiss B - 1")
        self.assertEqual(len({team for pair in pairs for team in pair}), 12)

        results = self.score_round(R1_SCORES)
        order = self.standings_order()
        ranks = [
            self.get_text(f"{STANDING_ROWS}:nth-child({i}) td:nth-child(1)") for i in range(1, 13)
        ]
        self.assertEqual(ranks, [str(i) for i in range(1, 13)])
        winners = [winner for winner, _ in results]
        losers = [loser for _, loser in results]
        self.assertEqual(order[:6], winners)
        self.assertEqual(order[6:], [losers[i] for i in (5, 4, 3, 1, 2, 0)])

        pairs = self.card_pairs("Round 2 Matches")
        self.assertEqual(len(pairs), 6)
        expected = {frozenset((order[i], order[i + 1])) for i in range(0, 12, 2)}
        self.assertEqual({frozenset(pair) for pair in pairs}, expected)

    def test_seeded_swiss_flow_regression(self) -> None:
        self.start_tournament()
        self.assert_element("#seeding-seeded[aria-pressed='true']")
        self.run_swiss()

        by_seed = self.names_by_seed()
        pairs = self.card_pairs("Swiss B - 1")
        self.assertEqual(
            {frozenset(pair) for pair in pairs},
            {frozenset((by_seed[i], by_seed[11 - i])) for i in range(6)},
        )
        self.assertRegex("\n".join(el.text for el in self.find_elements(MATCH_CARDS)), SEED_IN_NAME)

        self.score_round(R1_SCORES)
        order = self.standings_order()
        pairs = self.card_pairs("Round 2 Matches")
        self.assertEqual(len(pairs), 6)
        expected = {frozenset((order[i], order[i + 1])) for i in range(0, 12, 2)}
        self.assertEqual({frozenset(pair) for pair in pairs}, expected)

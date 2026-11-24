"""An unseeded tournament's public pages do not present the draw as seeding."""

import datetime
import json
import re
from contextlib import ExitStack
from http import HTTPStatus
from unittest.mock import patch

import pytest
from django.test import Client
from seleniumbase import BaseCase

from server.core.models import Team, User
from server.tests.base import create_pool
from server.tests.localserver import APP_URL, running_test_server
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Match, SwissRound, Tournament, TournamentField

NAMES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel"]
SEED_IN_NAME = re.compile(r"\(\d+\)")
RANK_CELLS = "table tbody tr th"
MATCH_CARDS = "div.rounded-lg.border.bg-white"


def reverse_order(team_ids: object) -> list[int]:
    return sorted(team_ids, reverse=True)  # type: ignore[call-overload]


@pytest.mark.django_db(transaction=True)
class TestUnseededPublicIntegration(BaseCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def build(self, seeded: bool = False) -> Tournament:
        """Pool A (seeds 1-4) and Swiss B (seeds 5-8), started, nothing played."""
        self.tournament = Tournament.objects.create(
            event=open_event(title="Nationals", type="OPN"), status=Tournament.Status.SCHEDULING
        )
        for name in NAMES:
            self.tournament.teams.add(Team.objects.create(name=name))
        staff = User.objects.create_user(
            "staff@example.com", "staff@example.com", "pw", is_staff=True
        )
        self.api = Client()
        self.api.force_login(staff)
        if seeded:
            self.tournament.initial_seeding = {
                str(i + 1): t.id for i, t in enumerate(self.tournament.teams.order_by("name"))
            }
            self.tournament.current_seeding = self.tournament.initial_seeding
            self.tournament.save()
        else:
            with patch("server.tournament.utils.draw_order", reverse_order):
                self.put(f"/api/tournament/{self.tournament.id}/seeded", {"seeded": False})
            self.tournament.refresh_from_db()
        create_pool("A", self.tournament, [1, 2, 3, 4])
        for match in Match.objects.filter(pool__isnull=False):
            slot = {seed: n for n, seed in enumerate([1, 2, 3, 4], 1)}
            slots = (slot[match.placeholder_seed_1], slot[match.placeholder_seed_2])
            match.name = f"A{slots[0]} vs A{slots[1]}"
            match.save()
        self.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 3, "seeding": [5, 6, 7, 8], "sequence_number": 1, "name": "B"},
        )
        self.post(f"/api/tournament/start/{self.tournament.id}")
        return self.tournament

    def put(self, url: str, body: dict[str, object]) -> None:
        response = self.api.put(url, json.dumps(body), content_type="application/json")
        self.assertEqual(response.status_code, HTTPStatus.OK, response.content)

    def post(self, url: str, body: dict[str, object] | None = None) -> None:
        response = self.api.post(url, json.dumps(body or {}), content_type="application/json")
        self.assertEqual(response.status_code, HTTPStatus.OK, response.content)

    def play(self, **match_filter: object) -> None:
        for match in Match.objects.filter(**match_filter).order_by("id"):
            self.post(f"/api/match/{match.id}/score", {"team_1_score": 15, "team_2_score": 9})

    def play_swiss_round(self, number: int) -> None:
        self.play(swiss_round=SwissRound.objects.get(), sequence_number=number)

    def schedule(self) -> None:
        field = TournamentField.objects.get_or_create(name="Field 1", tournament=self.tournament)[0]
        start = datetime.datetime.combine(
            self.tournament.event.start_date, datetime.time(9), tzinfo=datetime.UTC
        )
        matches = Match.objects.filter(tournament=self.tournament)
        offset = matches.filter(time__isnull=False).count()
        for i, match in enumerate(matches.filter(time__isnull=True).order_by("id"), offset):
            match.time = start + datetime.timedelta(hours=i)
            match.field = field
            match.save()

    def open_page(self, page: str = "") -> None:
        self.open(f"{APP_URL}/tournament/{self.tournament.event.slug}{page}")

    def show_swiss(self) -> None:
        self.open_page("/standings")
        self.click('button:contains("Swiss")')
        self.wait_for_text("Swiss B")

    def show_pool(self) -> None:
        self.open_page("/standings")
        self.wait_for_text("Pool A")

    def cards(self) -> str:
        self.wait_for_element(MATCH_CARDS)
        return "\n".join(el.text for el in self.find_elements(MATCH_CARDS))

    def column(self, selector: str) -> list[str]:
        self.wait_for_element(selector)
        return [el.text.strip() for el in self.find_elements(selector)]

    def test_no_initial_seeding_tab(self) -> None:
        self.build()
        self.open_page()
        self.wait_for_text("Overall Standings")
        self.assert_element('button:contains("SoTG")')
        self.assert_element_not_present('button:contains("Initial")')

    def test_standings_az_before_results_then_ranked(self) -> None:
        self.build()
        self.open_page()
        self.wait_for_element(RANK_CELLS)
        self.assertEqual(self.column(RANK_CELLS), [""] * 8)
        self.assertEqual(self.column("table tbody tr td:nth-child(2)"), sorted(NAMES))

        self.show_pool()
        self.assert_text_not_visible("SEED", "thead")
        self.assert_text("RANK", "thead")
        self.assertEqual(self.column("table tbody tr td:nth-child(1)")[:4], [""] * 4)
        self.assertEqual(
            self.column("table tbody tr td:nth-child(2)")[:4], ["Echo", "Foxtrot", "Golf", "Hotel"]
        )

        self.show_swiss()
        self.assertEqual(self.column("table tbody tr td:nth-child(1)"), [""] * 4)
        self.assertEqual(
            self.column("table tbody tr td:nth-child(2)"), ["Alpha", "Bravo", "Charlie", "Delta"]
        )

        self.play_swiss_round(1)
        self.show_swiss()
        self.assertEqual(self.column("table tbody tr td:nth-child(1)"), ["1", "2", "3", "4"])
        self.show_pool()
        self.assertEqual(self.column("table tbody tr td:nth-child(1)")[:4], [""] * 4)

        self.play(pool__isnull=False)
        self.show_pool()
        self.assertEqual(self.column("table tbody tr td:nth-child(1)")[:4], ["1", "2", "3", "4"])

        self.open_page()
        self.wait_for_element(RANK_CELLS)
        self.assertEqual(self.column(RANK_CELLS), [str(i) for i in range(1, 9)])
        self.assert_element_not_present("div.text-green-500 svg, div.text-red-500 svg")

    def test_round_one_cards_have_no_seed(self) -> None:
        self.build()
        self.show_pool()
        self.assertNotRegex(self.cards(), SEED_IN_NAME)
        self.assert_text("Echo")

        self.show_swiss()
        self.assert_text("Swiss B - 1")
        self.assertNotRegex(self.cards(), SEED_IN_NAME)

        self.schedule()
        self.open_page("/schedule")
        self.wait_for_element("table tbody tr")
        self.assert_text("SW B - 1")
        self.assertNotRegex(self.get_text("table"), r"SW B - 1\n\d+ v \d+")

        self.assertNotRegex(self.cards(), SEED_IN_NAME)

    def test_round_two_cards_show_rank(self) -> None:
        self.build()
        self.play_swiss_round(1)
        self.show_swiss()
        self.assert_text("Round 2 Matches")
        self.assertEqual(len(SEED_IN_NAME.findall(self.cards())), 4)

        self.schedule()
        self.open_page("/schedule")
        self.wait_for_element("table tbody tr")
        self.assertRegex(self.get_text("table"), r"[1-4] v [1-4]")

    def test_seeded_tournament_unchanged(self) -> None:
        self.build(seeded=True)
        self.open_page()
        self.wait_for_text("Overall Standings")
        self.assert_element('button:contains("Initial")')

        self.show_pool()
        self.assert_text("SEED", "thead")
        self.assertRegex(self.cards(), SEED_IN_NAME)
        self.assertEqual(self.column("table tbody tr td:nth-child(1)")[:4], ["1", "2", "3", "4"])

        self.show_swiss()
        self.assertRegex(self.cards(), SEED_IN_NAME)

        self.schedule()
        self.open_page("/schedule")
        self.wait_for_element("table tbody tr")
        self.assertRegex(self.get_text("table"), r"SW B - 1\n\d+ v \d+")

        self.play_swiss_round(1)
        self.play(pool__isnull=False)
        Tournament.objects.filter(id=self.tournament.id).update(
            current_seeding={str(i + 1): t for i, t in enumerate(reversed(self.seed_ids()))}
        )
        self.open_page()
        self.wait_for_element(RANK_CELLS)
        self.assert_element("div.text-green-500 svg, div.text-red-500 svg")

    def seed_ids(self) -> list[int]:
        self.tournament.refresh_from_db()
        return [self.tournament.initial_seeding[str(i + 1)] for i in range(8)]

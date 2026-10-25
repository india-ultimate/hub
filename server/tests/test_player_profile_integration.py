import datetime
from contextlib import ExitStack

import pytest
from django.utils.timezone import now
from seleniumbase import BaseCase

from server.core.models import Team, User
from server.tests import test_ui
from server.tests.base import create_event, create_player
from server.tests.localserver import APP_URL, running_test_server
from server.tournament.models import (
    Match,
    MatchEvent,
    MatchStats,
    Registration,
    SpiritScore,
    Tournament,
)


@pytest.mark.django_db(transaction=True)
class TestPlayerProfileIntegration(BaseCase):
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

    def setUp(self, masterqa_mode: bool = False) -> None:
        super().setUp()
        user = User.objects.create(username="ananya", first_name="Ananya", last_name="Rao")
        self.player = create_player(user)
        self.player.gender = "F"
        self.player.match_up = "F"
        self.player.save()
        self.pirates = Team.objects.create(name="Pune Pirates")
        self.crabs = Team.objects.create(name="Sand Crabs")
        self.older = self.make_tournament("Goa Beach Hat", 30, self.crabs)
        self.newer = self.make_tournament("Pune Open", 60, self.pirates)
        self.newer.current_seeding = {"3": self.pirates.id}
        self.newer.save()
        self.add_stats(self.newer)

    def make_tournament(
        self, title: str, days: int, team: Team, role: str = "PLA", status: str = "COM"
    ) -> Tournament:
        event = create_event(title)
        event.start_date = now().date() + datetime.timedelta(days=days)
        event.end_date = event.start_date + datetime.timedelta(days=2)
        event.save()
        tournament = Tournament.objects.create(event=event, status=status)
        Registration.objects.create(event=event, team=team, player=self.player, role=role)
        return tournament

    def add_stats(self, tournament: Tournament) -> None:
        spirit = SpiritScore.objects.create(
            rules=2,
            fouls=2,
            fair=2,
            positive=2,
            communication=2,
            total=10,
            mvp_v2=self.player,
            msp_v2=self.player,
        )
        match = Match.objects.create(
            tournament=tournament,
            sequence_number=1,
            time=now(),
            team_1=self.pirates,
            team_2=self.crabs,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            spirit_score_team_1=spirit,
            spirit_score_team_2=SpiritScore.objects.create(
                rules=2, fouls=2, fair=2, positive=2, communication=2, total=10
            ),
            self_spirit_score_team_1=SpiritScore.objects.create(
                rules=2, fouls=2, fair=2, positive=2, communication=2, total=10
            ),
        )
        MatchStats.objects.create(
            match=match,
            tournament=tournament,
            initial_possession=self.pirates,
            current_possession=self.crabs,
        )

    def test_profile_shows_history(self) -> None:
        self.open(f"{APP_URL}/player/{self.player.slug}")
        self.assert_text("Ananya Rao", "h1")
        self.assert_text("2 tournaments · 2 teams")
        for tile in ("mvp", "msp"):
            self.assert_text(tile.upper(), f'[data-tile="{tile}"]')
            self.assertEqual(self.get_text(f'[data-tile="{tile}"] div:first-child'), "1")
        self.assert_text("3rd")
        self.assertEqual(self.get_text("body").count("Stats not tracked at this tournament"), 1)
        self.assertNotIn("since", self.get_text("body").lower())

    def test_singular_chip_and_no_logo_element(self) -> None:
        MatchEvent.objects.create(
            stats=MatchStats.objects.get(tournament=self.newer),
            team=self.pirates,
            type="BL",
            block_by=self.player,
        )
        self.open(f"{APP_URL}/player/{self.player.slug}")
        self.assert_text("Female matching")
        card = 'article:contains("Pune Open")'
        self.assert_text("1 block", card)
        self.assertNotIn("1 blocks", self.get_text(card))
        self.assert_element_absent(f"{card} [data-logo]")

    def test_tournament_logo_renders_when_set(self) -> None:
        self.older.logo_light = "tournament_logos/goa.png"
        self.older.save()
        self.open(f"{APP_URL}/player/{self.player.slug}")
        self.assert_element('article:contains("Goa Beach Hat") img[data-logo]')

    def test_direct_visit_shows_breadcrumbs(self) -> None:
        url = f"{APP_URL}/player/{self.player.slug}"
        self.open(url)
        self.assert_element('nav[aria-label="Breadcrumb"]')
        self.assert_element_absent("[data-back-pill]")
        self.refresh()
        self.assert_text("Ananya Rao", "h1")
        self.assert_text("Pune Open")

    def test_back_pill_when_arriving_from_a_page(self) -> None:
        self.open(f"{APP_URL}/tournaments")
        self.execute_script(
            "history.pushState({from: {label: 'Pune Open · Leaderboard',"
            f" tournamentSlug: '{self.newer.event.slug}'}}}}, '', '/player/{self.player.slug}');"
            "dispatchEvent(new PopStateEvent('popstate'))"
        )
        self.assert_text("Pune Open · Leaderboard", "[data-back-pill]")
        self.assert_element_absent('nav[aria-label="Breadcrumb"]')
        self.assert_text("AT PUNE OPEN")

    def test_unknown_slug_not_found(self) -> None:
        self.open(f"{APP_URL}/player/nobody")
        self.assert_text("We couldn't find that player")

    def open_with_state(self, label: str, tournament: Tournament | None = None) -> None:
        self.open(f"{APP_URL}/tournaments")
        slug = f"'{tournament.event.slug}'" if tournament else "undefined"
        self.execute_script(
            f"history.pushState({{from: {{label: '{label}', tournamentSlug: {slug}}}}}, '',"
            f" '/player/{self.player.slug}'); dispatchEvent(new PopStateEvent('popstate'))"
        )

    def test_pinned_card_is_not_repeated(self) -> None:
        self.open_with_state("Pune Open · Leaderboard", self.newer)
        self.assert_text("AT PUNE OPEN")
        self.assert_element("article.ring-2")
        self.assert_element('div.grid article:contains("Goa Beach Hat")')
        self.assert_element_absent('div.grid article:contains("Pune Open")')

    def test_back_pill_returns_to_previous_page(self) -> None:
        self.open_with_state("Tournaments")
        self.click("[data-back-pill]")
        self.wait_for_element_absent("h1:contains('Ananya Rao')")
        self.assertTrue(self.get_current_url().endswith("/tournaments"))

    def test_roles_and_live_badge(self) -> None:
        self.make_tournament("Coached Cup", 90, self.crabs, role="COACH")
        self.make_tournament("Live Open", 120, self.pirates, status="LIV")
        self.open(f"{APP_URL}/player/{self.player.slug}")
        card = 'article:contains("Coached Cup")'
        self.assert_text("Coached, so no playing stats", card)
        self.assertNotIn("goals", self.get_text(card))
        self.assert_text("Live", 'article:contains("Live Open")')

    def test_earlier_tournaments_fold_away(self) -> None:
        for n in range(4):
            self.make_tournament(f"Extra {n}", 90 + n, self.crabs)
        self.open(f"{APP_URL}/player/{self.player.slug}")
        self.assert_text("Show 2 earlier tournaments")
        self.assertEqual(len(self.find_elements("article")), 4)
        self.click('button:contains("Show 2 earlier tournaments")')
        self.assertEqual(len(self.find_elements("article")), 6)
        self.assert_element_absent('button:contains("earlier tournament")')

    def test_failed_load_offers_retry(self) -> None:
        self.open(f"{APP_URL}/tournaments")
        self.execute_script(
            "window.realFetch = window.fetch;"
            "window.fetch = (u, ...a) => String(u).includes('/api/player-profile/')"
            " ? Promise.reject(new TypeError('offline')) : window.realFetch(u, ...a);"
            f"history.pushState({{}}, '', '/player/{self.player.slug}');"
            "dispatchEvent(new PopStateEvent('popstate'))"
        )
        self.assert_text("We couldn't load this profile", '[role="alert"]')
        self.execute_script("window.fetch = window.realFetch")
        self.click('button:contains("Try again")')
        self.assert_text("Ananya Rao", "h1")

    def test_roster_row_links_to_profile(self) -> None:
        slug = self.newer.event.slug
        self.open(f"{APP_URL}/tournament/{slug}/team/{self.pirates.slug}/roster")
        self.click('a:contains("Ananya Rao")')
        self.assert_text("Ananya Rao", "h1")
        self.assert_text("Pune Open · Pune Pirates roster", "[data-back-pill]")

    def test_dashboard_profile_card(self) -> None:
        self.sign_in_as(self.player.user)
        self.open(f"{APP_URL}/dashboard")
        self.click('a:contains("Your public profile")')
        self.assert_text("Ananya Rao", "h1")

    def test_leaderboard_round_trip(self) -> None:
        stats = MatchStats.objects.get(tournament=self.newer)
        for n in range(30):
            user = User.objects.create(
                username=f"p{n}", first_name=f"Player{n:02}", last_name="Roe"
            )
            other = create_player(user)
            Registration.objects.create(
                event=self.newer.event, team=self.pirates, player=other, role="PLA"
            )
            MatchEvent.objects.create(
                stats=stats,
                team=self.pirates,
                type="SC",
                scored_by=self.player,
                assisted_by=other,
            )
        self.set_window_size(1100, 700)
        self.open(f"{APP_URL}/tournament/{self.newer.event.slug}/leaderboard")
        self.click("button#assists-tab")
        self.wait_for_element('a[href^="/player/"]')
        self.assertIn("tab=assists", self.get_current_url())
        row = '[role="listitem"]:nth-of-type(20) a'
        self.scroll_to(row)
        self.sleep(1)
        before = self.execute_script("return window.scrollY")
        self.assertGreater(before, 100)
        name = self.get_text(row).splitlines()[1].split(" (")[0]
        self.click(row)
        self.assert_text(name, "h1")
        self.assert_text("Pune Open · Leaderboard", "[data-back-pill]")
        self.assert_text("AT PUNE OPEN")
        self.click("[data-back-pill]")
        self.wait_for_element('a[href^="/player/"]')
        self.assertIn("tab=assists", self.get_current_url())
        self.assertIn("bg-blue-600", self.get_attribute("button#assists-tab", "class"))
        self.sleep(0.5)
        after = self.execute_script("return window.scrollY")
        self.assertLess(abs(after - before), 60)

import datetime
from contextlib import ExitStack

import pytest
from django.utils.timezone import now
from selenium.webdriver.common.keys import Keys
from seleniumbase import BaseCase

from server.core.models import Player, Team, User
from server.season.models import Season
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
from server.utils import today

# (days from today, opponent key, [(score for, score against)], placement)
HISTORY = [
    (-10, "bb", [(15, 9), (12, 13)], 3),
    (-150, "bb", [(15, 11)], 1),
    (-300, "dd", [(15, 14)], 2),
    (-450, "bb", [(10, 15)], 5),
    (-600, "dd", [(15, 5)], 4),
    (-750, "bb", [(15, 12)], 6),
    (-900, "dd", [(9, 15)], 7),
    (-1050, "bb", [(15, 8)], 8),
]


@pytest.mark.django_db(transaction=True)
class TestTeamProfileIntegration(BaseCase):
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
        day = today()
        Season.objects.create(
            name="Now",
            start_date=day - datetime.timedelta(days=100),
            end_date=day + datetime.timedelta(days=200),
        )
        self.admin = User.objects.create(username="asha", first_name="Asha", last_name="Verma")
        self.team = Team.objects.create(
            name="Learning to Fly", city="Pune", state_ut="MH", category="Club"
        )
        self.team.admins.add(self.admin)
        self.opponents = {
            "bb": Team.objects.create(name="Bangalore Breakers"),
            "dd": Team.objects.create(name="Delhi Dynamos"),
        }
        self.captain = self.person("Ananya", "Rao")
        self.mvp = self.person("Meera", "Iyer")
        self.coach = self.person("Vikram", "Singh")
        self.tournaments: list[Tournament] = []
        for days, key, scores, place in HISTORY:
            self.tournaments.append(self.play(days, key, scores, place))
        newest = self.tournaments[0]
        self.bench = self.person("Rahul", "Bench")
        for player, role, playing in (
            (self.captain, "CAP", True),
            (self.mvp, "DFLT", True),
            (self.coach, "COACH", False),
            (self.bench, "DFLT", False),
        ):
            Registration.objects.create(
                event=newest.event, team=self.team, player=player, role=role, is_playing=playing
            )
        stats = MatchStats.objects.create(
            match=Match.objects.get(tournament=newest, sequence_number=1),
            tournament=newest,
            initial_possession=self.team,
            current_possession=self.team,
        )
        for scorer, assister in ((self.captain, self.mvp), (self.captain, self.mvp)):
            MatchEvent.objects.create(
                stats=stats, team=self.team, type="SC", scored_by=scorer, assisted_by=assister
            )
        MatchEvent.objects.create(stats=stats, team=self.team, type="BL", block_by=self.mvp)
        self.url = f"{APP_URL}/team/{self.team.slug}"

    def person(self, first: str, last: str) -> Player:
        user = User.objects.create(username=first.lower(), first_name=first, last_name=last)
        return create_player(user)

    def spirit(self, mvp: Player | None = None) -> SpiritScore:
        return SpiritScore.objects.create(
            rules=2, fouls=2, fair=2, positive=2, communication=2, total=10, mvp_v2=mvp
        )

    def play(
        self,
        days: int,
        key: str,
        scores: list[tuple[int, int]],
        place: int | None,
        status: str = "COM",
    ) -> Tournament:
        event = create_event(f"Open {days}")
        event.start_date = today() + datetime.timedelta(days=days)
        event.end_date = event.start_date + datetime.timedelta(days=2)
        event.location = "Bengaluru"
        event.save()
        tournament = Tournament.objects.create(event=event, status=status)
        opponent = self.opponents[key]
        tournament.teams.add(self.team, opponent)
        if place:
            tournament.current_seeding = {str(place): self.team.id}
            tournament.save()
        for i, (mine, theirs) in enumerate(scores, 1):
            Match.objects.create(
                tournament=tournament,
                sequence_number=i,
                status="COM",
                time=now() + datetime.timedelta(days=days, minutes=i),
                team_1=self.team,
                team_2=opponent,
                score_team_1=mine,
                score_team_2=theirs,
                placeholder_seed_1=1,
                placeholder_seed_2=2,
                spirit_score_team_1=self.spirit(self.mvp),
                spirit_score_team_2=self.spirit(),
            )
        return tournament

    def matches(self, key: str | None = None) -> list[tuple[int, int]]:
        return [s for _, k, scores, _ in HISTORY for s in scores if key is None or k == key]

    def wins(self, scores: list[tuple[int, int]]) -> int:
        return sum(1 for mine, theirs in scores if mine > theirs)

    def test_hero_and_summary(self) -> None:
        self.open(self.url)
        self.assert_text("Learning to Fly", "h1")
        self.assert_text("Club")
        self.assert_text("Pune, Maharashtra")
        self.assert_text(f"{len(HISTORY)} tournaments · {len(self.matches())} games")
        self.assertNotIn("since", self.get_text("body").lower())

    def test_stat_tiles(self) -> None:
        self.open(self.url)
        played = self.matches()
        wins = self.wins(played)
        losses = len(played) - wins
        self.assert_text(f"{wins}\u2013{losses}", '[data-tile="record"]')
        self.assert_text("WON\u2013LOST", '[data-tile="record"]')
        self.assert_text(f"{round(wins / len(played) * 100)}%", '[data-tile="win-rate"]')
        self.assertEqual(self.get_text('[data-tile="titles"] dd'), "1")
        self.assertEqual(self.get_text('[data-tile="titles"] dt').lower(), "tournament won")
        self.assertEqual(self.get_text('[data-tile="podiums"] dd'), "3")
        self.assertIn("bg-green-50", self.get_attribute('[data-tile="titles"]', "class"))
        self.assertIn("bg-yellow-50", self.get_attribute('[data-tile="spirit"]', "class"))
        self.assert_text("10.0", '[data-tile="spirit"]')

    def test_no_title_or_podium_tiles_without_podiums(self) -> None:
        for tournament, place in zip(self.tournaments, range(4, 12), strict=False):
            tournament.current_seeding = {str(place): self.team.id}
            tournament.save()
        self.open(self.url)
        self.assert_element('[data-tile="record"]')
        self.assert_element_absent('[data-tile="titles"]')
        self.assert_element_absent('[data-tile="podiums"]')

    def test_recent_form_rows_and_opponent_link(self) -> None:
        self.open(self.url)
        rows = 'section[aria-labelledby="form-heading"] li'
        self.assertEqual(len(self.find_elements(rows)), 5)
        self.assert_text("Recent matches", "#form-heading")
        self.assertNotIn("Latest first", self.get_text("body"))
        letters = self.get_text('section[aria-labelledby="form-heading"] ol')
        self.assertIn("15\u20139", letters)
        self.assertIn("12\u201313", letters)
        self.assertIn("W", letters)
        self.assertIn("L", letters)
        self.click(f'{rows} a:contains("Bangalore Breakers")')
        self.assert_text("Bangalore Breakers", "h1")
        self.assertTrue(self.get_current_url().endswith(f"/team/{self.opponents['bb'].slug}"))

    def test_season_roster_and_player_link(self) -> None:
        self.open(self.url)
        roster = 'section[aria-labelledby="roster-heading"]'
        self.assert_text("This season", roster)
        self.assert_text("Captain", roster)
        self.assert_text("Coach", roster)
        self.assert_text("Meera Iyer", roster)
        groups = self.find_elements(f"{roster} ul")
        self.assertEqual(len(groups), 2)
        self.assertIn("Ananya Rao", groups[0].text)
        self.assertNotIn("Vikram Singh", groups[0].text)
        self.assertNotIn("Rahul Bench", groups[0].text)
        self.assertIn("Vikram Singh", groups[1].text)
        self.assertIn("Rahul Bench", groups[1].text)
        self.assertIn("non-players", self.get_text(roster).lower())
        self.assertNotIn("staff", self.get_text(roster).lower())
        self.click(f'{roster} a:contains("Ananya Rao")')
        self.assert_text("Ananya Rao", "h1")
        self.assertTrue(self.get_current_url().endswith(f"/player/{self.captain.slug}"))
        self.assert_text("Learning to Fly", "[data-back-pill]")

    def test_leaders(self) -> None:
        self.open(self.url)
        goals = '[data-leaders="goals"]'
        self.assert_text("Ananya Rao", goals)
        self.assertEqual(self.get_text(f"{goals} li:first-child b"), "2")
        self.assert_text("Meera Iyer", '[data-leaders="assists"]')
        self.assert_text("Meera Iyer", '[data-leaders="blocks"]')
        self.assertEqual(
            self.get_text('[data-leaders="mvp"] li:first-child b'), str(len(self.matches()))
        )
        self.assert_element_absent('[data-leaders="msp"]')

    def test_history_groups_and_folds(self) -> None:
        self.open(self.url)
        history = 'section[aria-labelledby="history-heading"]'
        self.assertEqual(len(self.find_elements(f"{history} article")), 6)
        years = {t.event.start_date.year for t in self.tournaments[:6]}
        headings = [e.text for e in self.find_elements(f"{history} h3")]
        self.assertEqual(headings, [str(y) for y in sorted(years, reverse=True)])
        self.assert_text("Show 2 earlier tournaments", history)
        self.assert_text("1st", history)
        self.assert_text("W\u2013L 1\u20131", history)
        self.click('button:contains("Show 2 earlier tournaments")')
        self.assertEqual(len(self.find_elements(f"{history} article")), 8)
        self.assert_element_absent('button:contains("earlier tournament")')

    def test_focus_lands_on_first_new_card(self) -> None:
        self.open(self.url)
        self.click('button:contains("Show 2 earlier tournaments")')
        self.wait_for_element("[data-first-new]")
        title = self.get_text("[data-first-new] a")
        focused = self.execute_script(
            "return document.activeElement.closest('[data-first-new]') !== null"
        )
        self.assertTrue(focused, title)
        self.assertIn(self.tournaments[6].event.title, title)

    def test_matches_and_roster_link(self) -> None:
        self.open(self.url)
        slug = self.tournaments[0].event.slug
        card = f'article:has(a[href="/tournament/{slug}"])'
        self.click(f'{card} a:contains("Matches & roster")')
        self.assertTrue(
            self.get_current_url().endswith(f"/tournament/{slug}/team/{self.team.slug}")
        )

    def test_head_to_head(self) -> None:
        self.open(self.url)
        h2h = 'section[aria-labelledby="h2h-heading"]'
        bb = self.matches("bb")
        self.assert_text("Bangalore Breakers", h2h)
        self.assert_text(f"{len(bb)} games", h2h)
        self.assert_text(f"{self.wins(bb)}\u2013{len(bb) - self.wins(bb)}", h2h)
        self.click(f'{h2h} a:contains("Delhi Dynamos")')
        self.assert_text("Delhi Dynamos", "h1")

    def test_empty_team(self) -> None:
        empty = Team.objects.create(name="Fresh Team")
        self.open(f"{APP_URL}/team/{empty.slug}")
        self.assert_text("Fresh Team", "h1")
        self.assert_text("No tournaments yet")
        self.assert_element_absent('[data-tile="record"]')

    def test_unknown_team_not_found(self) -> None:
        self.open(f"{APP_URL}/team/nobody-here")
        self.assert_text("We couldn't find that team", "h1")
        self.assert_element('a:contains("Browse teams")')

    def test_admin_sees_edit_buttons(self) -> None:
        self.sign_in_as(self.admin)
        self.open(self.url)
        self.assert_text("Edit name")
        self.assert_element('a:contains("Edit details")')
        self.assertTrue(
            self.get_attribute('a:contains("Edit details")', "href").endswith(
                f"/team/{self.team.slug}/edit"
            )
        )

    def test_anonymous_sees_no_edit_buttons(self) -> None:
        self.open(self.url)
        self.assert_text("Learning to Fly", "h1")
        self.assert_element_absent('button:contains("Edit name")')
        self.assert_element_absent('a:contains("Edit details")')

    def test_tournament_team_header_links_here(self) -> None:
        slug = self.tournaments[0].event.slug
        self.open(f"{APP_URL}/tournament/{slug}/team/{self.team.slug}")
        self.assert_element_absent("h1 a")
        self.assert_element_absent("div.my-2 a")
        self.assert_element("h1 + div a")
        self.assert_text("View team profile", "h1 + div a")
        self.click('h1 + div a:contains("View team profile")')
        self.assert_text("This season")
        self.assertTrue(self.get_current_url().endswith(f"/team/{self.team.slug}"))

    def test_no_horizontal_scroll_at_narrowest_width(self) -> None:
        self.set_window_size(375, 900)
        self.open(self.url)
        self.assert_text("Recent matches")
        self.click('button:contains("Show 2 earlier tournaments")')
        overflow = self.execute_script(
            "const d = document.documentElement; return d.scrollWidth - d.clientWidth"
        )
        self.assertLessEqual(overflow, 0)

    def nationals(
        self, title: str, rank: int, typ: str, skill: str | None, **tags: str
    ) -> Tournament:
        event = create_event(title)
        event.start_date = today() - datetime.timedelta(days=20)
        event.end_date = event.start_date + datetime.timedelta(days=2)
        event.stage, event.type, event.skill_division, event.level = "Nationals", typ, skill, "Club"
        for field, value in tags.items():
            setattr(event, field, value)
        event.save()
        return Tournament.objects.create(
            event=event, status="COM", current_seeding={str(rank): self.team.id}
        )

    def seed_rankings(self) -> list[Tournament]:
        made = [
            self.nationals("Nationals 2026 Elite", 1, "MXD", "Elite"),
            self.nationals("Nationals 2026 Challenger", 4, "MXD", "Challenger"),
            self.nationals("Opens Nationals (Challenger)", 1, "OPN", "Challenger"),
            self.nationals("Opens Nationals (Elite)", 1, "OPN", "Elite"),
            self.nationals("Womens Nationals", 3, "WMN", None),
            self.nationals("Masters Nationals", 5, "MXD", None, age="Masters"),
        ]
        return made

    def test_rankings_badges(self) -> None:
        made = self.seed_rankings()
        Tournament.objects.filter(pk__in=[made[1].pk, made[3].pk]).update(current_seeding={})
        self.open(self.url)
        self.assert_element('ul[aria-label="National rankings"]')
        badges = self.find_elements("a[data-ranking]")
        self.assertEqual(len(badges), 4)
        texts = [b.text for b in badges]
        self.assertIn("#1", texts[0])
        self.assertIn("Mixed \u00b7 Elite", texts[0])
        self.assertIn("Nationals 2026", texts[0])
        self.assertEqual(texts[0].count("Elite"), 1)
        self.assertIn("Opens \u00b7 Challenger", texts[1])
        self.assertIn("#3", texts[2])
        self.assertIn("Womens", texts[2])
        self.assertIn("#5", texts[3])
        self.assertIn("Masters Mixed", texts[3])
        classes = [b.get_attribute("class") for b in badges]
        self.assertIn("border-l-amber-400", classes[0])
        self.assertNotIn("amber", classes[1])
        self.assertIn("border-l-gray-200", classes[1])
        self.assertIn("border-l-orange-500", classes[2])
        self.assertIn("border-l-gray-200", classes[3])
        self.assertEqual(
            self.execute_script(
                "return document.querySelector('a[data-ranking]').textContent.includes('Ranked 1st, ')"
            ),
            True,
        )
        href = self.get_attribute("a[data-ranking]", "href")
        self.assertTrue(href.endswith(f"/tournament/{made[0].event.slug}/team/{self.team.slug}"))
        self.click("a[data-ranking]")
        self.assert_text("Learning to Fly", "h1")
        self.assertIn(f"/tournament/{made[0].event.slug}/team/", self.get_current_url())

    def test_no_rankings_list_when_unranked(self) -> None:
        self.open(self.url)
        self.assert_text("Learning to Fly", "h1")
        self.assert_element_absent('ul[aria-label="National rankings"]')

    def test_team_links_are_not_underlined(self) -> None:
        self.open(self.url)
        self.assert_text("Recent matches")
        classes = self.execute_script(
            "return [...document.querySelectorAll('a[href^=\"/team/\"], section a')]"
            ".map(a => a.className).join(' ')"
        )
        self.assertNotIn("underline", classes)

    def add_roster(
        self, days: int, typ: str, first: str, last: str, team: Team | None = None
    ) -> None:
        team = team or self.team
        event = create_event(f"{typ} Cup {team.name}")
        event.start_date = today() + datetime.timedelta(days=days)
        event.end_date = event.start_date + datetime.timedelta(days=2)
        event.type = typ
        event.save()
        Tournament.objects.create(event=event, status="COM")
        Registration.objects.create(
            event=event, team=team, player=self.person(first, last), role="DFLT"
        )

    def test_roster_division_tabs(self) -> None:
        self.add_roster(-20, "OPN", "Zara", "Khan")
        self.add_roster(-30, "WMN", "Priya", "Das")
        self.open(self.url)
        self.assert_element('[role="tablist"][aria-label="Roster by division"]')
        tabs = "[role=tablist] [role=tab]"
        self.assertTrue(self.find_elements(tabs)[0].text.startswith("Mixed 2"))
        self.assertEqual(
            [t.text.split()[0] for t in self.find_elements(tabs)], ["Mixed", "Opens", "Womens"]
        )
        selected = lambda i: self.get_attribute(f"#roster-tab-{i}", "aria-selected")  # noqa: E731
        self.assertEqual([selected(i) for i in range(3)], ["true", "false", "false"])
        self.assert_text("Meera Iyer", "#roster-panel")
        self.assertEqual(self.get_attribute("#roster-panel", "role"), "tabpanel")
        self.click("#roster-tab-1")
        self.assert_text("Zara Khan", "#roster-panel")
        self.assertNotIn("Meera Iyer", self.get_text("#roster-panel"))
        self.assertEqual(selected(1), "true")
        self.send_keys("#roster-tab-1", Keys.ARROW_RIGHT)
        self.assert_text("Priya Das", "#roster-panel")
        self.assertEqual(selected(2), "true")
        self.assertEqual(self.execute_script("return document.activeElement.id"), "roster-tab-2")
        self.assertEqual(self.get_attribute("#roster-tab-2", "aria-controls"), "roster-panel")
        self.assertEqual(self.get_attribute("#roster-panel", "aria-labelledby"), "roster-tab-2")
        self.assertEqual(self.get_attribute("#roster-tab-2", "tabindex"), "0")
        self.send_keys("#roster-tab-2", Keys.ARROW_RIGHT)
        self.assertEqual(selected(0), "true")
        self.send_keys("#roster-tab-0", Keys.ARROW_LEFT)
        self.assertEqual(selected(2), "true")
        self.send_keys("#roster-tab-2", Keys.HOME)
        self.assertEqual(selected(0), "true")
        self.send_keys("#roster-tab-0", Keys.END)
        self.assertEqual(selected(2), "true")
        self.assertEqual(self.get_attribute("#roster-tab-0", "tabindex"), "-1")

    def test_single_division_has_no_tablist(self) -> None:
        self.open(self.url)
        self.assert_text("Meera Iyer", "#roster-panel")
        self.assert_element_absent('[role="tablist"]')

    def test_roster_tab_resets_when_navigating_to_another_team(self) -> None:
        self.add_roster(-20, "OPN", "Zara", "Khan")
        rival = self.opponents["bb"]
        self.add_roster(-15, "MXD", "Nina", "Paul", rival)
        self.add_roster(-25, "OPN", "Omar", "Ali", rival)
        self.open(f"{APP_URL}/team/{rival.slug}")
        self.assert_text("Nina Paul", "#roster-panel")
        self.click('section[aria-labelledby="h2h-heading"] a:contains("Learning to Fly")')
        self.assert_text("Learning to Fly", "h1")
        self.click("#roster-tab-1")
        self.assertEqual(self.get_attribute("#roster-tab-1", "aria-selected"), "true")
        self.click('section[aria-labelledby="form-heading"] li a:contains("Bangalore Breakers")')
        self.assert_text("Bangalore Breakers", "h1")
        self.assert_text("Nina Paul", "#roster-panel")
        self.assertEqual(self.get_attribute("#roster-tab-0", "aria-selected"), "true")
        self.assertEqual(self.get_attribute("#roster-tab-0", "tabindex"), "0")
        self.assertEqual(self.get_attribute("#roster-tab-1", "tabindex"), "-1")

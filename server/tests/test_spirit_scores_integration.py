"""A director saving the spirit form keeps the scores the match already has."""

import datetime
from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.core.models import Team, UCPerson, User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Match, Pool, SpiritScore, Tournament, UCRegistration


@pytest.mark.django_db(transaction=True)
class TestSpiritScoresIntegration(BaseCase):
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

    def test_saving_with_no_edits_keeps_the_saved_scores(self) -> None:
        event = open_event(title="Nationals", type="OPN")
        tournament = Tournament.objects.create(
            event=event, status=Tournament.Status.LIVE, use_uc_registrations=True
        )
        one = Team.objects.create(name="Alpha")
        two = Team.objects.create(name="Bravo")
        pool = Pool.objects.create(
            tournament=tournament,
            sequence_number=1,
            name="A",
            initial_seeding={"1": one.id, "2": two.id},
            results={},
        )
        captain = UCPerson.objects.create(
            email="captain@example.com", first_name="Asha", last_name="Rao", slug="asha-rao"
        )
        UCRegistration.objects.create(event=event, team=one, person=captain, roles=["player"])
        saved = SpiritScore.objects.create(
            rules=4,
            fouls=3,
            fair=4,
            positive=3,
            communication=4,
            total=18,
            mvp=captain,
            comments="Great game",
        )
        match = Match.objects.create(
            tournament=tournament,
            pool=pool,
            sequence_number=1,
            status=Match.Status.COMPLETED,
            time=datetime.datetime.now(datetime.UTC),
            team_1=one,
            team_2=two,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            spirit_score_team_1=saved,
        )
        staff = User.objects.create_user(
            "staff@example.com", "staff@example.com", "pw", is_staff=True
        )

        self.sign_in_as(staff)
        self.open(f"{APP_URL}/tournament-manager")
        self.select_option_by_text("select#tournaments", "Nationals")
        self.click('button:contains("Add Spirit Score")')
        rules = 'dialog[open] input[name="spirit_score_team_1.rules"]'
        self.wait_for_element_visible(rules, timeout=5)
        self.assertEqual("4", self.get_value(rules))
        self.assertEqual(
            "2", self.get_value('dialog[open] input[name="spirit_score_team_2.rules"]')
        )

        self.click('dialog[open] button[type="submit"]')
        self.wait_for_text("Updated Score!", "dialog[open]", timeout=5)

        match.refresh_from_db()
        score = match.spirit_score_team_1
        assert score is not None  # noqa: S101 - narrows the type
        self.assertEqual(
            (4, 3, 4, 3, 4),
            (score.rules, score.fouls, score.fair, score.positive, score.communication),
        )
        self.assertEqual(captain, score.mvp)
        self.assertEqual("Great game", score.comments)

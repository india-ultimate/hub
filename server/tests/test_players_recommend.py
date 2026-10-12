from server.core.models import Team
from server.tests.base import ApiBaseTestCase
from server.tournament.models import Registration


class TestRecommendPlayers(ApiBaseTestCase):
    def test_recommend_lists_players_who_registered_with_the_team(self) -> None:
        team = Team.objects.create(name="Tigers", slug="tigers")
        Registration.objects.create(event=self.event, player=self.player, team=team)
        self.client.force_login(self.user)

        response = self.client.get("/api/players/recommend?team_slug=tigers")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, response.json()["count"])
        self.assertEqual(self.player.id, response.json()["items"][0]["id"])

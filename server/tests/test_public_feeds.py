"""What the India Ultimate website reads from the hub."""

import datetime

from django.utils.timezone import now

from server.announcements.models import Announcement
from server.core.models import User
from server.tests.test_tournament_api_perf import TournamentApiTestCase
from server.tournament.models import Match, Tournament

URL = "/api/public/matches"


class TestRecentMatches(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        Tournament.objects.filter(pk=self.tournament.pk).update(status=Tournament.Status.LIVE)

    def at(self, days: float) -> Match:
        match = self.make_match()
        Match.objects.filter(pk=match.pk).update(time=now() + datetime.timedelta(days=days))
        return match

    def test_five_days_either_side_in_time_order(self) -> None:
        later, earlier = self.at(4.9), self.at(-4.9)
        self.at(-5.1), self.at(5.1)
        body = self.client.get(URL).json()
        self.assertEqual([earlier.id, later.id], [match["id"] for match in body])
        event = self.tournament.event
        self.assertEqual({"slug": event.slug, "title": event.title}, body[0]["tournament"])

    def test_skips_draft_tournaments(self) -> None:
        self.at(1)
        Tournament.objects.filter(pk=self.tournament.pk).update(status=Tournament.Status.DRAFT)
        self.assertEqual([], self.client.get(URL).json())

    def test_queries_dont_grow_with_matches(self) -> None:
        self.at(1)
        self.assert_constant(URL, lambda: [self.at(1) for _ in range(5)])

    def test_no_personal_data(self) -> None:
        self.at(1)
        self.assert_no_personal_data(URL)


class TestAnnouncementHeadlines(TournamentApiTestCase):
    def test_published_headlines_newest_first_without_content(self) -> None:
        author = User.objects.create(username="staff@example.com", is_staff=True)
        post = {"author": author, "content": "<p>Secret body</p>"}
        Announcement.objects.create(title="Old", is_published=True, **post)
        Announcement.objects.create(
            title="Members", is_published=True, is_members_only=True, **post
        )
        Announcement.objects.create(title="Draft", **post)

        response = self.client.get("/api/public/announcements")

        body = response.json()
        self.assertEqual(["Members", "Old"], [headline["title"] for headline in body])
        self.assertEqual({"title", "slug", "type", "is_members_only", "created_at"}, set(body[0]))
        self.assertTrue(body[0]["is_members_only"])
        self.assertNotIn("Secret body", response.content.decode())

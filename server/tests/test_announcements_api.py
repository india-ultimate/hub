from django.test import TestCase

from server.announcements.models import Announcement
from server.core.models import Player, User
from server.season.models import Season
from server.subscription.models import Subscription

SECRET = "<p>Selection trials are on Sunday</p>"


class AnnouncementAccessTestCase(TestCase):
    def setUp(self) -> None:
        self.author = User.objects.create(username="author@example.com", is_staff=True)
        self.members_only = Announcement.objects.create(
            title="Trials",
            content=SECRET,
            author=self.author,
            is_members_only=True,
            is_published=True,
            action_text="Sign up",
            action_url="https://example.com/trials",
        )
        self.public = Announcement.objects.create(
            title="Nationals",
            content="<p>Nationals in March</p>",
            author=self.author,
            is_published=True,
        )

    def _user(self, email: str, *, staff: bool = False, player: bool = True) -> User:
        user = User.objects.create(username=email, email=email, is_staff=staff)
        if player:
            Player.objects.create(user=user, date_of_birth="1990-01-01")
        return user

    def _subscribe(self, user: User, *, active: bool) -> None:
        season = Season.current()
        assert season is not None  # noqa: S101 - the seeded seasons cover today
        Subscription.objects.create(
            player=user.player_profile,
            season=season,
            start_date=season.start_date,
            end_date=season.end_date,
            is_active=active,
        )

    def _detail(self, user: User, slug: str) -> dict[str, object]:
        self.client.force_login(user)
        response = self.client.get(f"/api/announcements/{slug}")
        self.assertEqual(200, response.status_code, response.content)
        data: dict[str, object] = response.json()
        return data

    def _listed(self, user: User) -> dict[str, dict[str, object]]:
        self.client.force_login(user)
        response = self.client.get("/api/announcements/")
        self.assertEqual(200, response.status_code, response.content)
        return {a["slug"]: a for a in response.json()}

    def assert_readable(self, data: dict[str, object]) -> None:
        self.assertTrue(data["can_read"])
        self.assertEqual(SECRET, data["content"])
        self.assertEqual("Sign up", data["action_text"])
        self.assertEqual("https://example.com/trials", data["action_url"])

    def assert_locked(self, data: dict[str, object]) -> None:
        self.assertFalse(data["can_read"])
        self.assertEqual("", data["content"])
        self.assertIsNone(data["action_text"])
        self.assertIsNone(data["action_url"])
        self.assertEqual("Trials", data["title"])

    def test_non_member_gets_members_only_post_without_content(self) -> None:
        user = self._user("nonmember@example.com")
        self.assert_locked(self._detail(user, self.members_only.slug))
        self.assert_locked(self._listed(user)[self.members_only.slug])

    def test_inactive_subscription_is_locked(self) -> None:
        user = self._user("lapsed@example.com")
        self._subscribe(user, active=False)
        self.assert_locked(self._detail(user, self.members_only.slug))

    def test_user_without_player_profile_is_locked(self) -> None:
        user = self._user("noprofile@example.com", player=False)
        self.assert_locked(self._detail(user, self.members_only.slug))

    def test_member_reads_members_only_post(self) -> None:
        user = self._user("member@example.com")
        self._subscribe(user, active=True)
        self.assert_readable(self._detail(user, self.members_only.slug))
        self.assert_readable(self._listed(user)[self.members_only.slug])

    def test_staff_without_membership_reads_members_only_post(self) -> None:
        user = self._user("staff@example.com", staff=True, player=False)
        self.assert_readable(self._detail(user, self.members_only.slug))
        self.assert_readable(self._listed(user)[self.members_only.slug])

    def test_public_post_is_readable_by_non_member(self) -> None:
        user = self._user("reader@example.com")
        data = self._detail(user, self.public.slug)
        self.assertTrue(data["can_read"])
        self.assertEqual("<p>Nationals in March</p>", data["content"])

    def test_anonymous_cannot_fetch_announcements(self) -> None:
        self.assertEqual(
            401, self.client.get(f"/api/announcements/{self.members_only.slug}").status_code
        )
        self.assertEqual(401, self.client.get("/api/announcements/").status_code)

    def test_non_staff_does_not_see_drafts(self) -> None:
        draft = Announcement.objects.create(
            title="Draft", content="<p>Not yet</p>", author=self.author, is_published=False
        )
        user = self._user("reader@example.com")
        self.assertNotIn(draft.slug, self._listed(user))
        self.client.force_login(user)
        self.assertEqual(404, self.client.get(f"/api/announcements/{draft.slug}").status_code)

    def test_staff_sees_drafts(self) -> None:
        draft = Announcement.objects.create(
            title="Draft", content="<p>Not yet</p>", author=self.author, is_published=False
        )
        user = self._user("staff@example.com", staff=True)
        self.assertIn(draft.slug, self._listed(user))
        self.assertEqual("<p>Not yet</p>", self._detail(user, draft.slug)["content"])

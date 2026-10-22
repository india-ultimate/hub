from django.test import SimpleTestCase

from server.announcements.models import Announcement
from server.core.models import Player, Team, User
from server.mcp.markdown import to_markdown
from server.tests.base import create_event
from server.tests.test_mcp_invitations import McpToolCase
from server.tournament.models import Registration
from server.wrapped.models import PlayerWrapped

HTML = (
    "<h2>Nationals &amp; more</h2><p>Dates are <strong>out</strong>.<br>See "
    '<a href="https://x.org/dates">the page</a>.</p>'
    "<ul><li>Bring ID</li><li>Bring water</li></ul>"
    "<script>alert(1)</script><p>&nbsp;</p><p>Fee&nbsp;is &#8377;500</p>"
)


class TestToMarkdown(SimpleTestCase):
    def test_a_post_reads_as_markdown(self) -> None:
        self.assertEqual(
            "## Nationals & more\n\nDates are **out**.\nSee [the page](https://x.org/dates).\n\n"
            "- Bring ID\n- Bring water\n\nFee is ₹500",
            to_markdown(HTML),
        )

    def test_plain_text_and_nothing(self) -> None:
        self.assertEqual("hello", to_markdown("hello"))
        self.assertEqual("", to_markdown(""))


class TestGetMyStats(McpToolCase):
    def setUp(self) -> None:
        super().setUp()
        self.me = Player.objects.create(user=self.user, date_of_birth="2000-01-01")

    def register(self) -> Registration:
        team = Team.objects.create(name="Dragons")
        return Registration.objects.create(
            player=self.me, team=team, event=create_event("Nationals"), points=3
        )

    def wrapped(self, year: int, scores: int = 12) -> PlayerWrapped:
        return PlayerWrapped.objects.create(
            player=self.me,
            year=year,
            total_scores=scores,
            top_teammates_i_assisted=[{"player_name": "Ravi", "player_id": 9, "count": 4}],
        )

    def test_registrations_without_the_player_record(self) -> None:
        self.register()

        data = self.data("get_my_stats", {})

        [row] = data["registrations"]
        self.assertEqual("Nationals", row["event_name"])
        self.assertEqual("Dragons", row["team_name"])
        self.assertEqual(3, row["points"])
        self.assertNotIn("player", row)
        self.assertNotIn("a@x.com", str(data))
        self.assertIn("not your wards", data["coverage"])
        self.assertIsNone(data["wrapped"])

    def test_the_newest_wrapped_year_by_default(self) -> None:
        self.wrapped(2024, scores=5)
        self.wrapped(2025, scores=12)

        data = self.data("get_my_stats", {})

        self.assertEqual(2025, data["wrapped"]["year"])
        self.assertEqual(12, data["wrapped"]["total_scores"])
        self.assertEqual([2025, 2024], data["wrapped_years"])
        self.assertEqual("Ravi", data["wrapped"]["top_teammates_i_assisted"][0]["player_name"])
        for hidden in ("id", "player", "created_at", "updated_at"):
            self.assertNotIn(hidden, data["wrapped"])

    def test_a_given_year(self) -> None:
        self.wrapped(2024, scores=5)
        self.wrapped(2025)

        self.assertEqual(5, self.data("get_my_stats", {"year": 2024})["wrapped"]["total_scores"])

    def test_a_year_without_wrapped_says_so(self) -> None:
        data = self.data("get_my_stats", {"year": 2019})

        self.assertIsNone(data["wrapped"])
        self.assertIn("2019", data["wrapped_note"])

    def test_someone_without_a_player_gets_empty_stats(self) -> None:
        self.me.delete()

        data = self.data("get_my_stats", {})

        self.assertEqual([], data["registrations"])
        self.assertIsNone(data["wrapped"])


class TestAnnouncements(McpToolCase):
    def setUp(self) -> None:
        super().setUp()
        self.poster = User.objects.create(
            username="p@x.com", email="p@x.com", first_name="Pia", last_name="Jain"
        )

    def by_poster(self, title: str, **kw: object) -> Announcement:
        return Announcement.objects.create(
            title=title, content=kw.pop("content", "<p>Body</p>"), author=self.poster, **kw
        )

    def test_lists_published_posts_newest_first_without_content(self) -> None:
        self.by_poster("Old", is_published=True)
        self.by_poster("New", is_published=True, is_members_only=True)
        self.by_poster("Draft")

        data = self.data("list_announcements", {})

        self.assertEqual(["New", "Old"], [a["title"] for a in data["announcements"]])
        first = data["announcements"][0]
        self.assertEqual("new", first["slug"])
        self.assertEqual("Pia Jain", first["author"])
        self.assertTrue(first["is_members_only"])
        self.assertFalse(first["can_read"])
        self.assertNotIn("content", first)
        self.assertEqual(2, data["total"])

    def test_pages_of_twenty(self) -> None:
        for n in range(25):
            self.by_poster(f"Post {n:02}", is_published=True)

        first = self.data("list_announcements", {})
        second = self.data("list_announcements", {"page": 2})

        self.assertEqual(20, len(first["announcements"]))
        self.assertTrue(first["has_more"])
        self.assertEqual(5, len(second["announcements"]))
        self.assertFalse(second["has_more"])

    def test_reads_a_post_as_markdown(self) -> None:
        self.by_poster("Dates", content=HTML, is_published=True, action_text="Register")

        data = self.data("get_announcement", {"slug": "dates"})

        self.assertEqual("Dates", data["title"])
        self.assertTrue(data["content_markdown"].startswith("## Nationals & more"))
        self.assertNotIn("<", data["content_markdown"])
        self.assertTrue(data["can_read"])
        self.assertEqual("Register", data["action_text"])

    def test_members_only_is_locked_for_a_non_member(self) -> None:
        self.by_poster(
            "Members", content="<p>Secret plan</p>", is_published=True, is_members_only=True
        )

        data = self.data("get_announcement", {"slug": "members"})

        self.assertFalse(data["can_read"])
        self.assertEqual("", data["content_markdown"])
        self.assertIn("members", data["locked"])
        self.assertNotIn("Secret", str(data))

    def test_members_only_is_open_to_staff(self) -> None:
        self.by_poster(
            "Members", content="<p>Secret plan</p>", is_published=True, is_members_only=True
        )
        self.user.is_staff = True
        self.user.save()

        data = self.data("get_announcement", {"slug": "members"})

        self.assertEqual("Secret plan", data["content_markdown"])
        self.assertNotIn("locked", data)

    def test_a_draft_is_not_found_for_others(self) -> None:
        self.by_poster("Draft")

        self.assertEqual(
            "Announcement not found", self.failure("get_announcement", {"slug": "draft"})
        )

    def test_a_bad_slug(self) -> None:
        self.assertTrue(self.failure("get_announcement", {"slug": "a/../b"}))

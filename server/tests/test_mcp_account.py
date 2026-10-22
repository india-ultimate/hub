import datetime

from server.committee.models import Committee
from server.committee.models import Role as CommitteeRole
from server.mcp.dispatch import ApiResponse, denied
from server.tests.base import create_event
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.tournament.models import Tournament


class TestDenied(McpProtocolTestCase):
    def test_401_and_403_say_not_allowed(self) -> None:
        for status in (401, 403):
            with self.subTest(status=status):
                result = denied(ApiResponse(status, {"message": "Only admins"}))

                self.assertTrue(result.is_error)
                self.assertEqual("Not allowed: Only admins", result.data["message"])

    def test_anything_else_is_hubs_message(self) -> None:
        result = denied(ApiResponse(400, {"message": "Bad dates"}))

        self.assertTrue(result.is_error)
        self.assertEqual("Bad dates", result.data["message"])


class TestWhoami(McpProtocolTestCase):
    def whoami(self) -> dict:  # type: ignore[type-arg]
        response = self.modern("tools/call", {"name": "whoami", "arguments": {}})
        data: dict = response.json()["result"]["structuredContent"]  # type: ignore[type-arg]
        return data

    def test_plain_user(self) -> None:
        data = self.whoami()

        self.assertEqual([], data["committees"])
        self.assertEqual([], data["directed_tournaments"])
        self.assertEqual([], data["volunteer_tournaments"])
        self.assertFalse(data["can_post_announcements"])
        self.assertEqual(["everyone"], data["roles"])

    def test_committee_director_and_volunteer(self) -> None:
        committee = Committee.objects.create(
            name="Comms", slug="comms", can_post_announcements=True
        )
        CommitteeRole.objects.create(
            committee=committee,
            user=self.user,
            title="Member",
            start_date=datetime.date(2020, 1, 1),
        )
        event = create_event("Nationals")
        tournament = Tournament.objects.create(event=event)
        tournament.directors.add(self.user)
        volunteered = Tournament.objects.create(event=create_event("Open"))
        volunteered.volunteers.add(self.user)

        data = self.whoami()

        self.assertEqual([{"name": "Comms", "slug": "comms"}], data["committees"])
        self.assertEqual(
            [{"event_slug": event.slug, "title": event.title}], data["directed_tournaments"]
        )
        self.assertEqual(
            [{"event_slug": volunteered.event.slug, "title": volunteered.event.title}],
            data["volunteer_tournaments"],
        )
        self.assertTrue(data["can_post_announcements"])
        self.assertEqual(["director", "everyone", "handler", "poster"], sorted(data["roles"]))

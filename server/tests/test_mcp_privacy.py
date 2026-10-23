"""No read tool shows anyone's email, phone or date of birth: not a stranger's, and not
the caller's own.

A stranger is on a roster, a series roster, a match and a public ticket, so they turn up
in lists. Every read tool a plain player, a team admin or staff can call is searched, whole.
"""

import datetime
import json
from typing import Any

from server.core.models import Player, User
from server.mcp.registry import TOOLS, roles_of
from server.registration.models import RosterEntry
from server.series.models import Series, SeriesRegistration
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_tools_tournaments import SLUG, TournamentToolsTestCase
from server.ticket.models import Ticket, TicketMessage
from server.tournament.models import Registration


def forms_of(email: str, phone: str, born: datetime.date) -> list[str]:
    return [
        email,
        email.upper(),
        phone,
        f"+91{phone}",
        f"+91 {phone}",
        born.isoformat(),
        born.strftime("%d/%m/%Y"),
        born.strftime("%m/%d/%Y"),
        born.strftime("%d-%m-%Y"),
        born.strftime("%d %b %Y"),
        born.strftime("%B %d, %Y"),
        born.strftime("%b %d, %Y"),
    ]


class TestStrangersStayPrivate(TournamentToolsTestCase):
    def stranger(self, tag: str, phone: str, born: datetime.date) -> Player:
        email = f"{tag}.hidden@example.org"
        user = User.objects.create(
            username=email, email=email, phone=phone, first_name=tag.title(), last_name="Hidden"
        )
        self.secrets += forms_of(email, phone, born)
        return Player.objects.create(user=user, date_of_birth=born, city="Pune")

    def viewer(self, tag: str, team: Any = None, staff: bool = False) -> str:
        email, phone, born = f"{tag}@x.com", f"98{len(self.secrets):08d}", datetime.date(1995, 5, 5)
        user = User.objects.create(username=email, email=email, phone=phone, is_staff=staff)
        Player.objects.create(user=user, date_of_birth=born, city="Pune")
        self.secrets += forms_of(email, phone, born)
        if team:
            team.admins.add(user)
        make_token(user, tag, scope="hub:read")
        return tag

    def setUp(self) -> None:
        super().setUp()
        self.secrets: list[str] = []
        self.one = self.stranger("amit", "9123498765", datetime.date(2011, 7, 19))
        self.two = self.stranger("bina", "9876501234", datetime.date(1990, 3, 4))
        series = Series.objects.get(slug="nationals-series")
        registration = SeriesRegistration.objects.create(
            series=series, team=self.home, player=self.one
        )
        Registration.objects.create(
            event=self.event, team=self.home, player=self.one, series_registration=registration
        )
        RosterEntry.objects.create(event=self.event, team=self.teams[3], player=self.two)
        ticket = Ticket.objects.create(
            title="Roster help", description="Please check Amit", created_by=self.one.user
        )
        TicketMessage.objects.create(ticket=ticket, sender=self.one.user, message="Thanks")
        self.ticket = ticket
        self.viewers = {
            "plain": self.viewer("plain"),
            "other_admin": self.viewer("other", self.teams[2]),
            "own_admin": self.viewer("own", self.home),
            "second_admin": self.viewer("second", self.teams[3]),
            "staff": self.viewer("staff", staff=True),
        }

    def calls(self) -> list[tuple[str, dict[str, Any]]]:
        team = self.home.slug
        return [
            ("whoami", {}),
            ("search", {"query": "Hidden"}),
            ("search", {"query": "Amit", "kind": "player"}),
            ("get_tournament", {"event_slug": SLUG}),
            *(
                ("get_tournament", {"event_slug": SLUG, "view": view})
                for view in ("schedule", "standings", "spirit", "leaderboard")
            ),
            ("get_tournament", {"event_slug": SLUG, "view": "schedule", "team_slug": team}),
            ("get_match", {"match_id": self.first.pk}),
            ("list_match_rosters", {"match_id": self.first.pk}),
            ("get_series_roster", {"series_slug": "nationals-series", "team_slug": team}),
            ("list_tickets", {}),
            ("list_tickets", {"q": "Roster"}),
            ("get_ticket", {"ticket_id": self.ticket.pk}),
            ("list_announcements", {}),
            ("list_forms", {}),
            ("list_my_payments", {}),
            ("list_series_invitations", {}),
            ("get_my_stats", {}),
            ("get_readiness", {}),
            ("get_readiness", {"event_slug": SLUG}),
            ("get_documents", {"player_id": self.one.pk}),
            ("get_readiness", {"player_id": self.one.pk}),
            ("get_membership_options", {"player_ids": [self.one.pk, self.two.pk]}),
            ("list_team_events", {}),
            ("list_team_events", {"team_slug": team}),
            ("get_team_registration", {"event_slug": SLUG, "team_slug": team}),
            ("get_team_registration", {"event_slug": SLUG, "team_slug": self.teams[3].slug}),
            ("find_team_candidates", {"event_slug": SLUG, "team_slug": team}),
            ("find_team_candidates", {"event_slug": SLUG, "team_slug": team, "text": "Hidden"}),
            ("find_team_candidates", {"event_slug": SLUG, "team_slug": team, "text": "amit"}),
            ("find_team_candidates", {"event_slug": SLUG, "team_slug": self.teams[3].slug}),
            ("find_member", {"query": "Hidden"}),
            ("find_member", {"query": "amit.hidden@example.org"}),
            ("get_member_status", {"player_id": self.one.pk}),
            ("lookup_payment", {"email": "amit.hidden@example.org"}),
            ("get_staff_inbox", {}),
            ("list_service_requests", {"status": "all"}),
            ("get_membership_report", {"kind": "active"}),
        ]

    def test_no_read_tool_shows_contact_details_or_birthdays(self) -> None:
        seen = False
        for who, bearer in self.viewers.items():
            roles = roles_of(User.objects.get(username=f"{bearer}@x.com"))
            for name, arguments in self.calls():
                tool = TOOLS[name]
                self.assertFalse(tool.writes, name)
                if not tool.visible_to(User.objects.get(username=f"{bearer}@x.com"), roles):
                    continue
                body = json.dumps(self.call(name, arguments, bearer))
                seen = seen or "Amit" in body
                for secret in self.secrets:
                    self.assertNotIn(secret, body, f"{name} {arguments} showed {secret} to {who}")
        self.assertTrue(seen, "the stranger never appeared, so nothing was checked")

    def test_every_read_tool_a_player_or_team_admin_has_is_covered(self) -> None:
        reached = {name for name, _ in self.calls()}
        covered = {
            "get_announcement",
            "get_form",
            "get_payment_account_report",
        }
        for tool in TOOLS.values():
            if tool.audience.value in ("everyone", "team_admin") and not tool.writes:
                self.assertIn(tool.name, reached | covered, tool.name)

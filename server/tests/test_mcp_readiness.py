import datetime
import json
from typing import Any

from django.test import SimpleTestCase, override_settings

from server.accreditation.models import Accreditation
from server.core.models import (
    CollegeId,
    CommentaryInfo,
    Guardianship,
    Player,
    Team,
    User,
)
from server.mcp.tools.readiness import checklist
from server.registration.models import RosterEntry
from server.season.models import Season
from server.series.models import Series, SeriesRosterInvitation
from server.subscription.models import Subscription, SubscriptionPlan, SubscriptionType
from server.tests.base import create_event
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.tournament.models import Registration
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer

TODAY = datetime.date(2026, 10, 20)
HUB = "https://hub.example.org"


def full(**changes: Any) -> dict[str, Any]:
    player: dict[str, Any] = {
        "id": 1,
        "occupation": "Professional",
        "subscription": {"is_active": True, "waiver_valid": True, "coc_agreed": True},
        "accreditation": {"is_valid": True},
        "commentary_info": {"jersey_number": 7},
        "college_id": None,
    }
    return {**player, **changes}


def card(expiry: str, removed: str | None = None) -> dict[str, Any]:
    return {"expiry": expiry, "images_removed_at": removed}


class TestChecklist(SimpleTestCase):
    def test_a_full_profile_is_all_true(self) -> None:
        self.assertEqual(
            {
                "profile": True,
                "subscription": True,
                "waiver": True,
                "coc": True,
                "accreditation": True,
                "commentary_info": True,
                "college_id": True,
            },
            checklist(full(), TODAY),
        )

    def test_no_subscription_fails_three(self) -> None:
        got = checklist(full(subscription=None), TODAY)
        self.assertEqual([False, False, False], [got["subscription"], got["waiver"], got["coc"]])

    def test_a_non_student_needs_no_college_id(self) -> None:
        self.assertTrue(checklist(full(), TODAY)["college_id"])

    def test_students_and_their_cards(self) -> None:
        student = {"occupation": "College-Student"}
        cases = [
            (card("2026-10-20"), True),
            (card("2026-10-19"), False),
            (card("2027-01-01", removed="2026-09-01"), False),
            (None, False),
        ]
        for college_id, expected in cases:
            with self.subTest(college_id=college_id):
                got = checklist(full(college_id=college_id, **student), TODAY)
                self.assertEqual(expected, got["college_id"])

    def test_an_invalid_accreditation_fails(self) -> None:
        self.assertFalse(checklist(full(accreditation={"is_valid": False}), TODAY)["accreditation"])
        self.assertFalse(checklist(full(accreditation=None), TODAY)["accreditation"])


@override_settings(PUBLIC_URL=HUB)
class ReadinessCase(McpProtocolTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.season = Season.objects.get(name="Season 2026-2027")
        self.me = self.make_player(self.user)
        ward_user = User.objects.create(username="w@x.com", first_name="Wren", last_name="Rao")
        self.ward = self.make_player(ward_user)
        Guardianship.objects.create(user=self.user, player=self.ward, relation="MO")
        stranger = User.objects.create(username="s@x.com", first_name="Sam", last_name="Roe")
        self.stranger = self.make_player(stranger)

    @staticmethod
    def make_player(user: User) -> Player:
        return Player.objects.create(user=user, date_of_birth="2000-01-01", city="Pune")

    def complete(self, player: Player) -> None:
        plan = SubscriptionPlan.objects.get(
            season=self.season, type=SubscriptionType.objects.get(slug="regular")
        )
        Subscription.objects.create(
            player=player,
            season=self.season,
            plan=plan,
            is_active=True,
            waiver_valid=True,
            coc_agreed=True,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        Accreditation.objects.create(
            player=player, is_valid=True, level="STD", date=TODAY, certificate="c.pdf"
        )
        CommentaryInfo.objects.create(
            player=player,
            jersey_number=7,
            ultimate_origin="a",
            ultimate_attraction="a",
            ultimate_fav_role="a",
            ultimate_fav_exp="a",
            interests="a",
            fun_fact="a",
        )

    def readiness(self, arguments: dict[str, Any]) -> dict[str, Any]:
        body = self.modern("tools/call", {"name": "get_readiness", "arguments": arguments})
        return dict(body.json()["result"])

    def data(self, arguments: dict[str, Any]) -> Any:
        result = self.readiness(arguments)
        self.assertFalse(result["isError"], result)
        self.assertNotIn("id", self.keys(result["structuredContent"]))
        return result["structuredContent"]


@override_settings(PUBLIC_URL=HUB)
class TestGetReadiness(ReadinessCase):
    def test_it_is_a_read_tool(self) -> None:
        listed = {t["name"]: t for t in self.modern("tools/list").json()["result"]["tools"]}
        self.assertTrue(listed["get_readiness"]["annotations"]["readOnlyHint"])
        self.assertTrue(listed["get_readiness"]["title"])

    def test_optional_items_do_not_block_play(self) -> None:
        self.complete(self.me)
        CommentaryInfo.objects.filter(player=self.me).delete()

        mine = self.data({})["players"][0]

        self.assertTrue(mine["ready"])
        self.assertEqual(
            [("commentary_info", False)],
            [(m["item"], m["required_to_play"]) for m in mine["missing"]],
        )

    def test_the_caller_and_each_ward_with_what_is_missing(self) -> None:
        self.complete(self.me)
        data = self.data({})
        mine, wards = data["players"]
        self.assertEqual(
            {
                "player_id": self.me.id,
                "full_name": "Asha Rao",
                "ready": True,
                "missing": [],
                "next_steps": [],
            },
            mine,
        )
        self.assertEqual(self.ward.id, wards["player_id"])
        self.assertFalse(wards["ready"])
        self.assertEqual(
            [
                ("subscription", "subscription"),
                ("waiver", "waiver"),
                ("coc", "code-of-conduct"),
                ("accreditation", "accreditation"),
                ("commentary_info", "commentary-info"),
            ],
            [
                (m["item"], m["fix_url"].removeprefix(f"{HUB}/").split("/")[0])
                for m in wards["missing"]
            ],
        )
        self.assertEqual(f"{HUB}/waiver/{self.ward.id}", wards["missing"][1]["fix_url"])

    def test_one_player_by_id(self) -> None:
        data = self.data({"player_id": self.ward.id})
        self.assertEqual([self.ward.id], [p["player_id"] for p in data["players"]])

    def test_a_stranger_is_refused_with_hubs_message(self) -> None:
        result = self.readiness({"player_id": self.stranger.id})
        self.assertTrue(result["isError"])
        self.assertEqual(
            "You can't see this player's details", result["structuredContent"]["message"]
        )

    def test_a_team_admin_sees_only_membership_for_a_rostered_player(self) -> None:
        self.complete(self.stranger)
        team = Team.objects.create(name="Roster Team", slug="roster-team")
        team.admins.add(self.user)
        RosterEntry.objects.create(event=create_event("Nationals"), team=team, player=self.stranger)

        data = self.data({"player_id": self.stranger.id})

        self.assertEqual(
            [
                {
                    "player_id": self.stranger.id,
                    "full_name": "Sam Roe",
                    "membership_active": True,
                    "note": "You can see only membership status for this player.",
                }
            ],
            data["players"],
        )
        self.assertNotIn("fix_url", json.dumps(data))

    def test_a_student_without_a_card_is_sent_to_upload_one(self) -> None:
        self.complete(self.me)
        self.me.occupation = "College-Student"
        self.me.save()
        CollegeId.objects.create(
            player=self.me, expiry="2020-01-01", card_front="f.jpg", card_back="b.jpg"
        )
        missing = self.data({})["players"][0]["missing"]
        self.assertEqual(
            [("college_id", f"{HUB}/college-id/{self.me.id}")],
            [(m["item"], m["fix_url"]) for m in missing],
        )

    def test_can_play_at_an_event(self) -> None:
        event = create_event("Gated")
        event.slug = "gated"
        event.is_subscription_needed = True
        event.start_date = self.season.start_date
        event.save()
        self.complete(self.me)
        data = self.data({"event_slug": "gated", "player_id": self.ward.id})
        self.assertEqual(
            {"ok": False, "reason": "Subscription missing"}, data["players"][0]["can_play"]
        )
        data = self.data({"event_slug": "gated"})
        self.assertEqual({"ok": True, "reason": None}, data["players"][0]["can_play"])

    def test_can_play_in_a_series(self) -> None:
        Series.objects.create(
            name="League",
            slug="league",
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            type="MXD",
            category="Club",
            series_roster_max_players=20,
            event_min_players_male=1,
            event_min_players_female=1,
            event_max_players_male=10,
            event_max_players_female=10,
        )
        self.complete(self.me)

        mine = self.data({"series_slug": "league"})["players"][0]["can_play_series"]
        wards = self.data({"series_slug": "league", "player_id": self.ward.id})["players"][0]

        self.assertEqual({"ok": True, "reason": None}, mine)
        self.assertEqual({"ok": False, "reason": "Subscription missing"}, wards["can_play_series"])
        self.assertNotIn("can_play", wards)

    def test_an_unknown_event_is_an_error(self) -> None:
        self.assertTrue(self.readiness({"event_slug": "nope"})["isError"])
        self.assertTrue(self.readiness({"series_slug": "nope"})["isError"])
        self.assertTrue(self.readiness({"event_slug": "bad slug!"})["isError"])

    def test_no_profile_gets_a_next_step(self) -> None:
        self.me.delete()
        Guardianship.objects.all().delete()
        data = self.data({})
        self.assertEqual([], data["players"])
        self.assertEqual(f"{HUB}/registration/me", data["next_step"]["url"])
        self.assertEqual(
            [{"item": "profile", "tool": "create_profile", "arguments": {"for": "me"}}],
            [
                {k: v for k, v in step.items() if k not in ("why", "required_to_play")}
                for step in data["next_steps"]
            ],
        )


@override_settings(PUBLIC_URL=HUB)
class TestNextSteps(ReadinessCase):
    def steps(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = self.data(arguments)["players"][0]["next_steps"]
        return steps

    def test_a_player_with_nothing_is_walked_through_in_order(self) -> None:
        steps = self.steps({"player_id": self.me.id})

        self.assertEqual(
            ["subscription", "waiver", "coc", "accreditation", "commentary_info"],
            [s["item"] for s in steps],
        )
        self.assertEqual(
            [
                ("get_membership_options", {"player_ids": [self.me.id]}),
                ("sign_document", {"player_id": self.me.id, "document": "waiver"}),
                ("sign_document", {"player_id": self.me.id, "document": "coc"}),
                ("create_upload_link", {"kind": "accreditation", "player_id": self.me.id}),
                ("update_profile", {"player_id": self.me.id}),
            ],
            [(s["tool"], s["arguments"]) for s in steps],
        )
        self.assertTrue(all(s["why"] for s in steps))
        self.assertIn("buy_membership", steps[0]["why"])
        self.assertIn("membership", steps[1]["why"])

    def test_a_college_student_is_also_sent_to_upload_a_card(self) -> None:
        self.me.occupation = "College-Student"
        self.me.save()

        steps = self.steps({"player_id": self.me.id})

        self.assertEqual(
            ["subscription", "waiver", "coc", "accreditation", "college_id", "commentary_info"],
            [s["item"] for s in steps],
        )
        self.assertEqual({"kind": "college_id", "player_id": self.me.id}, steps[4]["arguments"])

    def test_only_what_blocks_play_is_required_and_comes_first(self) -> None:
        self.me.occupation = "College-Student"
        self.me.save()

        steps = self.steps({"player_id": self.me.id})

        self.assertEqual(
            {
                "subscription": True,
                "waiver": True,
                "coc": True,
                "accreditation": True,
                "college_id": False,
                "commentary_info": False,
            },
            {s["item"]: s["required_to_play"] for s in steps},
        )
        flags = [s["required_to_play"] for s in steps]
        self.assertEqual(sorted(flags, reverse=True), flags)

    def test_an_unpaid_membership_order_points_to_the_existing_pay_link(self) -> None:
        order = RazorpayTransaction.objects.create(
            order_id="order_unpaid1",
            status="created",
            amount=5000,
            currency="INR",
            payment_id="",
            payment_signature="",
            user=self.user,
            season=self.season,
            type=RazorpayTransaction.TransactionTypeChoices.ANNUAL_SUBSCRIPTION,
        )
        RazorpayTransactionPlayer.objects.create(transaction=order, player=self.me, amount=5000)

        step = self.steps({"player_id": self.me.id})[0]

        self.assertEqual("subscription", step["item"])
        self.assertEqual("list_my_payments", step["tool"])
        self.assertEqual({"kind": "unpaid"}, step["arguments"])
        self.assertEqual(f"{HUB}/pay/order_unpaid1", step["pay_url"])
        self.assertTrue(step["required_to_play"])

    def test_a_failed_order_does_not_hide_the_membership_step(self) -> None:
        order = RazorpayTransaction.objects.create(
            order_id="order_failed1",
            status="failed",
            amount=5000,
            currency="INR",
            payment_id="",
            payment_signature="",
            user=self.user,
            season=self.season,
        )
        RazorpayTransactionPlayer.objects.create(transaction=order, player=self.me, amount=5000)

        step = self.steps({"player_id": self.me.id})[0]

        self.assertEqual("get_membership_options", step["tool"])
        self.assertNotIn("pay_url", step)

    def test_a_ready_player_has_no_steps(self) -> None:
        self.complete(self.me)

        self.assertEqual([], self.steps({"player_id": self.me.id}))

    def test_no_event_means_no_roster(self) -> None:
        self.assertNotIn("roster", self.data({})["players"][0])

    def make_event(self) -> Any:
        event = create_event("Nationals")
        event.slug = "nats"
        event.series = Series.objects.create(
            name="League",
            slug="league",
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            type="MXD",
            category="Club",
            series_roster_max_players=20,
            event_min_players_male=1,
            event_min_players_female=1,
            event_max_players_male=10,
            event_max_players_female=10,
        )
        event.save()
        self.team = Team.objects.create(name="Windmill", slug="windmill")
        return event

    def roster(self, player: Player) -> dict[str, Any]:
        data = self.data({"event_slug": "nats", "player_id": player.id})
        roster: dict[str, Any] = data["players"][0]["roster"]
        return roster

    def test_rostered(self) -> None:
        event = self.make_event()
        Registration.objects.create(event=event, team=self.team, player=self.me)

        got = self.roster(self.me)

        self.assertEqual(
            {"status": "rostered", "team_name": "Windmill", "team_slug": "windmill"}, got
        )
        steps = self.steps({"event_slug": "nats", "player_id": self.me.id})
        self.assertNotIn("roster", [s["item"] for s in steps])

    def test_rostered_but_not_playing(self) -> None:
        event = self.make_event()
        Registration.objects.create(event=event, team=self.team, player=self.me, is_playing=False)

        self.assertEqual("rostered_not_playing", self.roster(self.me)["status"])

    def test_on_an_unpaid_roster_entry(self) -> None:
        event = self.make_event()
        RosterEntry.objects.create(event=event, team=self.team, player=self.me)

        self.assertEqual("on_roster_unpaid", self.roster(self.me)["status"])
        last = next(
            s
            for s in self.steps({"event_slug": "nats", "player_id": self.me.id})
            if s["item"] == "roster"
        )
        self.assertEqual(("roster", None), (last["item"], last["tool"]))

    def test_invited_with_the_invitation_id(self) -> None:
        event = self.make_event()
        invitation = SeriesRosterInvitation.objects.create(
            series=event.series, from_user=self.stranger.user, to_player=self.me, team=self.team
        )

        got = self.roster(self.me)
        last = next(
            s
            for s in self.steps({"event_slug": "nats", "player_id": self.me.id})
            if s["item"] == "roster"
        )

        self.assertEqual("invited", got["status"])
        self.assertEqual(invitation.id, got["invitation_id"])
        self.assertEqual("answer_series_invitation", last["tool"])
        self.assertEqual({"invitation_id": invitation.id, "answer": "accept"}, last["arguments"])

    def test_a_wards_pending_invitation_is_shown_to_the_guardian(self) -> None:
        event = self.make_event()
        SeriesRosterInvitation.objects.create(
            series=event.series, from_user=self.stranger.user, to_player=self.ward, team=self.team
        )

        self.assertEqual("invited", self.roster(self.ward)["status"])

    def test_an_answered_invitation_does_not_count(self) -> None:
        event = self.make_event()
        SeriesRosterInvitation.objects.create(
            series=event.series,
            from_user=self.stranger.user,
            to_player=self.me,
            team=self.team,
            status="Declined",
        )

        self.assertEqual("not_on_a_team", self.roster(self.me)["status"])

    def test_not_on_any_team_is_told_to_ask_a_team_admin(self) -> None:
        self.make_event()

        last = next(
            s
            for s in self.steps({"event_slug": "nats", "player_id": self.me.id})
            if s["item"] == "roster"
        )

        self.assertEqual("not_on_a_team", self.roster(self.me)["status"])
        self.assertIsNone(last["tool"])
        self.assertIn("team admin", last["why"])

    def test_another_players_roster_is_not_shown(self) -> None:
        event = self.make_event()
        RosterEntry.objects.create(event=event, team=self.team, player=self.stranger)
        self.team.admins.add(self.user)

        player = self.data({"event_slug": "nats", "player_id": self.stranger.id})["players"][0]

        self.assertNotIn("roster", player)
        self.assertNotIn("windmill", json.dumps(player))


class TestNewcomerFlow(McpProtocolTestCase):
    def test_no_profile_then_create_then_next_steps(self) -> None:
        make_token(self.user, "wtok", scope="hub:read hub:write")

        first = self.call("get_readiness", {}, "wtok")["structuredContent"]
        self.assertEqual("create_profile", first["next_steps"][0]["tool"])

        profile = {
            "for": "me",
            "first_name": "Asha",
            "last_name": "Rao",
            "phone": "9999900000",
            "date_of_birth": "2000-01-01",
            "gender": "F",
            "match_up": "F",
            "city": "Pune",
        }
        asked = self.call("create_profile", profile, "wtok")["structuredContent"]
        created = self.call(
            "create_profile", {**profile, "confirmation": asked["confirmation"]}, "wtok"
        )["structuredContent"]
        player_id = created["player_id"]

        after = self.call("get_readiness", {}, "wtok")["structuredContent"]["players"][0]
        self.assertEqual(player_id, after["player_id"])
        self.assertEqual(
            ["subscription", "waiver", "coc", "accreditation", "commentary_info"],
            [s["item"] for s in after["next_steps"]],
        )

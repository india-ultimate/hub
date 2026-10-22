import datetime
import re
from pathlib import Path
from typing import Any
from unittest import mock

from django.test import SimpleTestCase, override_settings

from server.accreditation.models import Accreditation
from server.core.models import CommentaryInfo, Guardianship, Player, User
from server.mcp.tools.profile import DOCUMENTS
from server.season.models import Season
from server.subscription.models import Subscription, SubscriptionPlan, SubscriptionType
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer

MIN_PART = 20
HUB = "https://hub.example.org"
FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
ME = {
    "first_name": "Asha",
    "last_name": "Rao",
    "phone": "9999900000",
    "date_of_birth": "2000-01-01",
    "gender": "F",
    "match_up": "F",
    "city": "Pune",
}
KID = {
    "first_name": "Wren",
    "last_name": "Rao",
    "phone": "9999900001",
    "date_of_birth": "2014-03-04",
    "gender": "M",
    "match_up": "M",
    "city": "Pune",
}
COMMENTARY = {
    "jersey_number": 7,
    "ultimate_origin": "college",
    "ultimate_attraction": "the community",
    "ultimate_fav_role": "handler",
    "ultimate_fav_exp": "Nationals",
    "interests": "chess",
    "fun_fact": "tall",
}


class ProfileTestCase(McpProtocolTestCase):
    bearer = "wtok"

    def setUp(self) -> None:
        super().setUp()
        make_token(self.user, "wtok", scope="hub:read hub:write")
        self.season = Season.objects.get(name="Season 2026-2027")

    def confirmed(
        self, name: str, arguments: dict[str, Any], bearer: str = "wtok"
    ) -> dict[str, Any]:
        first = self.call(name, arguments, bearer)
        self.assertFalse(first["isError"], first)
        data = first["structuredContent"]
        if "needs_confirmation" not in data:
            return first
        return self.call(name, {**arguments, "confirmation": data["confirmation"]}, bearer)

    def make_player(self, user: User, dob: str = "2000-01-01") -> Player:
        return Player.objects.create(user=user, date_of_birth=dob, city="Pune")

    def subscribe(self, player: Player, **flags: Any) -> Subscription:
        plan = SubscriptionPlan.objects.get(
            season=self.season, type=SubscriptionType.objects.get(slug="regular")
        )
        return Subscription.objects.create(
            player=player,
            season=self.season,
            plan=plan,
            is_active=True,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            **flags,
        )


class TestCreateProfile(ProfileTestCase):
    def test_for_me_creates_the_callers_profile(self) -> None:
        asked = self.call("create_profile", {"for": "me", **ME})["structuredContent"]
        self.assertIn("a@x.com", asked["needs_confirmation"])
        self.assertFalse(Player.objects.filter(user=self.user).exists())

        result = self.confirmed("create_profile", {"for": "me", **ME})

        self.assertFalse(result["isError"], result)
        player = Player.objects.get(user=self.user)
        self.assertEqual(player.id, result["structuredContent"]["player_id"])
        self.assertEqual("Pune", player.city)
        self.assertNotIn("id", self.keys(result["structuredContent"]))

    def test_match_up_follows_gender_like_the_web_form(self) -> None:
        args = {k: v for k, v in ME.items() if k != "match_up"}

        result = self.confirmed("create_profile", {"for": "me", **args})

        self.assertFalse(result["isError"], result)
        self.assertEqual(ME["gender"], Player.objects.get(user=self.user).match_up)

    def test_for_me_twice_gets_hubs_refusal(self) -> None:
        self.make_player(self.user)

        result = self.confirmed("create_profile", {"for": "me", **ME})

        self.assertTrue(result["isError"])
        self.assertEqual("Player already exists", result["structuredContent"]["message"])

    def test_for_ward_makes_the_caller_the_guardian(self) -> None:
        self.make_player(self.user)
        args = {"for": "ward", **KID, "email": "wren@x.com", "relation": "MO"}

        asked = self.call("create_profile", args)["structuredContent"]["needs_confirmation"]
        self.assertIn("Wren Rao", asked)
        self.assertIn("wren@x.com", asked)
        self.assertIn("guardian", asked)
        result = self.confirmed("create_profile", args)

        self.assertFalse(result["isError"], result)
        ward = Player.objects.get(user__username="wren@x.com")
        self.assertEqual(self.user, ward.guardianship.user)
        self.assertEqual("MO", ward.guardianship.relation)
        self.assertEqual("Student", ward.occupation)

    def test_for_ward_without_email_says_so(self) -> None:
        args = {"for": "ward", **KID, "relation": "FA"}

        asked = self.call("create_profile", args)["structuredContent"]["needs_confirmation"]

        self.assertIn("no email", asked)

    def test_an_adult_cannot_be_a_ward(self) -> None:
        result = self.confirmed("create_profile", {"for": "ward", **ME, "relation": "MO"})

        self.assertTrue(result["isError"])
        self.assertIn("Only minors can have a guardian", result["structuredContent"]["message"])
        self.assertFalse(Player.objects.exists())

    def test_a_minor_registers_with_a_guardian(self) -> None:
        args = {
            "for": "me_minor",
            **KID,
            "relation": "LG",
            "guardian_first_name": "Ravi",
            "guardian_last_name": "Rao",
            "guardian_email": "ravi@x.com",
            "guardian_phone": "9999900002",
        }

        asked = self.call("create_profile", args)["structuredContent"]["needs_confirmation"]
        self.assertIn("ravi@x.com", asked)
        result = self.confirmed("create_profile", args)

        self.assertFalse(result["isError"], result)
        player = Player.objects.get(user=self.user)
        self.assertEqual("ravi@x.com", player.guardianship.user.email)

    def test_missing_fields_are_named(self) -> None:
        for mode, expected in [
            ("me", "city"),
            ("ward", "relation"),
            ("me_minor", "guardian_email"),
        ]:
            with self.subTest(mode):
                fields = {k: v for k, v in KID.items() if k != "city"} if mode == "me" else KID
                result = self.call("create_profile", {"for": mode, **fields})

                self.assertTrue(result["isError"])
                self.assertIn(expected, result["structuredContent"]["message"])

    def test_bad_values_are_refused_before_asking(self) -> None:
        for bad in [{"gender": "X"}, {"state_ut": "ZZ"}, {"date_of_birth": "soon"}]:
            with self.subTest(bad):
                result = self.call("create_profile", {"for": "me", **ME, **bad})
                self.assertTrue(result["isError"])
                self.assertIn(next(iter(bad)), result["structuredContent"]["message"])

    def test_it_never_registers_others_and_has_a_closed_schema(self) -> None:
        listed = {
            t["name"]: t for t in self.modern("tools/list", bearer="wtok").json()["result"]["tools"]
        }
        schema = listed["create_profile"]["inputSchema"]

        self.assertEqual(["me", "me_minor", "ward"], sorted(schema["properties"]["for"]["enum"]))
        self.assertEqual(["F", "M", "O"], sorted(schema["properties"]["gender"]["enum"]))
        self.assertEqual(["F", "M"], sorted(schema["properties"]["match_up"]["enum"]))
        self.assertEqual(["FA", "LG", "MO"], sorted(schema["properties"]["relation"]["enum"]))
        self.assertIn("MH", schema["properties"]["state_ut"]["enum"])
        self.assertFalse(schema["additionalProperties"])
        self.assertTrue(listed["create_profile"]["title"])

    def test_a_read_only_token_cannot_write(self) -> None:
        body = self.modern(
            "tools/call", {"name": "create_profile", "arguments": {"for": "me", **ME}}
        )

        self.assertEqual(403, body.status_code)
        self.assertFalse(Player.objects.exists())


class TestUpdateProfile(ProfileTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.me = self.make_player(self.user)
        self.user.phone = "9999900000"
        self.user.save()
        self.me.state_ut = "MH"
        self.me.gender = "F"
        self.me.match_up = "F"
        self.me.occupation = "Other"
        self.me.save()

    def test_it_changes_only_what_was_named(self) -> None:
        args = {"player_id": self.me.id, "changes": {"city": "Delhi"}}

        asked = self.call("update_profile", args)["structuredContent"]["needs_confirmation"]
        self.assertIn("Pune", asked)
        self.assertIn("Delhi", asked)
        result = self.confirmed("update_profile", args)

        self.assertFalse(result["isError"], result)
        self.me.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual("Delhi", self.me.city)
        self.assertEqual("MH", self.me.state_ut)
        self.assertEqual("Other", self.me.occupation)
        self.assertEqual("F", self.me.gender)
        self.assertEqual(datetime.date(2000, 1, 1), self.me.date_of_birth)
        self.assertEqual(("Asha", "9999900000"), (self.user.first_name, self.user.phone))

    def test_a_ward_can_be_edited_by_the_guardian(self) -> None:
        ward = self.make_player(
            User.objects.create(username="w@x.com", first_name="Wren"), "2014-01-01"
        )
        ward.gender, ward.match_up = "M", "M"
        ward.save()
        Guardianship.objects.create(user=self.user, player=ward, relation="MO")

        result = self.confirmed(
            "update_profile", {"player_id": ward.id, "changes": {"last_name": "Roe"}}
        )

        self.assertFalse(result["isError"], result)
        ward.user.refresh_from_db()
        self.assertEqual("Roe", ward.user.last_name)

    def test_commentary_info_merges_with_what_is_there(self) -> None:
        CommentaryInfo.objects.create(player=self.me, **COMMENTARY)

        result = self.confirmed(
            "update_profile",
            {"player_id": self.me.id, "changes": {"commentary_info": {"jersey_number": 9}}},
        )

        self.assertFalse(result["isError"], result)
        info = CommentaryInfo.objects.get(player=self.me)
        self.assertEqual((9, "handler"), (info.jersey_number, info.ultimate_fav_role))

    def test_first_commentary_info_needs_every_field(self) -> None:
        result = self.call(
            "update_profile",
            {"player_id": self.me.id, "changes": {"commentary_info": {"jersey_number": 9}}},
        )

        self.assertTrue(result["isError"])
        self.assertIn("fun_fact", result["structuredContent"]["message"])

    def test_first_commentary_info_with_every_field(self) -> None:
        result = self.confirmed(
            "update_profile",
            {"player_id": self.me.id, "changes": {"commentary_info": COMMENTARY}},
        )

        self.assertFalse(result["isError"], result)
        self.assertTrue(CommentaryInfo.objects.filter(player=self.me).exists())

    def test_a_stranger_is_denied(self) -> None:
        other = self.make_player(User.objects.create(username="s@x.com", first_name="Sam"))

        result = self.call("update_profile", {"player_id": other.id, "changes": {"city": "X"}})

        self.assertTrue(result["isError"])
        self.assertIn("Not allowed", result["structuredContent"]["message"])
        other.refresh_from_db()
        self.assertEqual("Pune", other.city)

    def test_no_changes_is_an_error(self) -> None:
        result = self.call("update_profile", {"player_id": self.me.id, "changes": {}})

        self.assertTrue(result["isError"])

    def test_a_bad_value_is_named(self) -> None:
        result = self.call("update_profile", {"player_id": self.me.id, "changes": {"gender": "Z"}})

        self.assertTrue(result["isError"])
        self.assertIn("gender", result["structuredContent"]["message"])


class TestGetDocuments(ProfileTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.me = self.make_player(self.user)
        self.ward = self.make_player(
            User.objects.create(username="w@x.com", first_name="Wren"), "2014-01-01"
        )
        Guardianship.objects.create(user=self.user, player=self.ward, relation="MO")

    def docs(self, arguments: dict[str, Any]) -> Any:
        result = self.call("get_documents", arguments)
        self.assertFalse(result["isError"], result)
        return result["structuredContent"]

    def test_it_is_a_read_tool(self) -> None:
        listed = {t["name"]: t for t in self.modern("tools/list").json()["result"]["tools"]}
        self.assertTrue(listed["get_documents"]["annotations"]["readOnlyHint"])

    def test_the_caller_and_wards_by_default(self) -> None:
        data = self.docs({})

        self.assertEqual([self.me.id, self.ward.id], [p["player_id"] for p in data["players"]])
        mine = data["players"][0]
        self.assertEqual(
            {"signed": False, "signed_by": None, "signed_at": None, "valid": False}, mine["waiver"]
        )
        self.assertFalse(mine["coc"]["agreed"])
        self.assertFalse(mine["accreditation"]["present"])
        self.assertFalse(mine["college_id"]["present"])
        self.assertFalse(mine["vaccination"]["present"])
        self.assertFalse(mine["profile_picture"]["present"])
        self.assertFalse(mine["membership"]["active"])

    def test_signed_and_valid_documents(self) -> None:
        self.subscribe(
            self.me,
            waiver_valid=True,
            waiver_signed_by=self.user,
            waiver_signed_at=datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC),
            coc_agreed=True,
            coc_agreed_by=self.user,
        )
        Accreditation.objects.create(
            player=self.me,
            is_valid=True,
            level="ADV",
            date=datetime.date(2026, 1, 1),
            expiry_date=datetime.date(2027, 7, 1),
            certificate="secret/cert.pdf",
        )
        self.me.profile_pic_url = "https://img.example/p.jpg"
        self.me.save()

        mine = self.docs({"player_id": self.me.id})["players"][0]

        self.assertTrue(mine["waiver"]["valid"])
        self.assertEqual("Asha Rao", mine["waiver"]["signed_by"])
        self.assertTrue(mine["coc"]["agreed"])
        self.assertEqual(
            {"present": True, "level": "ADV", "expiry": "2027-07-01", "valid": True},
            mine["accreditation"],
        )
        self.assertTrue(mine["profile_picture"]["present"])
        self.assertTrue(mine["membership"]["active"])
        self.assertEqual("Regular Subscription", mine["membership"]["tier_name"])
        text = str(mine)
        self.assertNotIn("secret", text)
        self.assertNotIn("img.example", text)
        self.assertNotIn("id", self.keys(mine))

    def test_a_stranger_is_denied(self) -> None:
        other = self.make_player(User.objects.create(username="s@x.com", first_name="Sam"))

        result = self.call("get_documents", {"player_id": other.id})

        self.assertTrue(result["isError"])
        self.assertIn("Not allowed", result["structuredContent"]["message"])


@override_settings(PUBLIC_URL=HUB)
class TestSignDocument(ProfileTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.me = self.make_player(self.user)
        self.kid_user = User.objects.create(username="w@x.com", first_name="Wren", last_name="Rao")
        self.kid = self.make_player(self.kid_user, "2014-01-01")
        Guardianship.objects.create(user=self.user, player=self.kid, relation="MO")
        self.adult_ward_user = User.objects.create(
            username="c@x.com", first_name="Cal", last_name="Rao"
        )
        self.adult_ward = self.make_player(self.adult_ward_user)
        Guardianship.objects.create(user=self.user, player=self.adult_ward, relation="FA")

    def ask(self, player: Player, document: str = "waiver") -> dict[str, Any]:
        return self.call("sign_document", {"player_id": player.id, "document": document})

    def test_an_unpaid_membership_order_is_offered_before_signing(self) -> None:
        order = RazorpayTransaction.objects.create(
            order_id="order_unpaid",
            amount=100,
            currency="INR",
            status="created",
            user=self.user,
            season=Season.current(),
        )
        RazorpayTransactionPlayer.objects.create(transaction=order, player=self.me)

        result = self.ask(self.me)

        self.assertTrue(result["isError"])
        self.assertTrue(result["structuredContent"]["pay_url"].endswith("/pay/order_unpaid"))

    def test_an_adult_signs_for_themself(self) -> None:
        sub = self.subscribe(self.me)

        asked = self.ask(self.me)["structuredContent"]
        self.assertTrue(
            asked["needs_confirmation"].startswith("Sign the 2026-2027 waiver for Asha Rao (you)")
        )
        sub.refresh_from_db()
        self.assertFalse(sub.waiver_valid)
        result = self.confirmed("sign_document", {"player_id": self.me.id, "document": "waiver"})

        self.assertFalse(result["isError"], result)
        sub.refresh_from_db()
        self.assertTrue(sub.waiver_valid)
        self.assertEqual(self.user, sub.waiver_signed_by)

    def test_a_guardian_signs_for_a_minor(self) -> None:
        sub = self.subscribe(self.kid)

        asked = self.ask(self.kid)["structuredContent"]["needs_confirmation"]
        self.assertTrue(
            asked.startswith("Sign the 2026-2027 waiver for Wren Rao (your ward) as Asha Rao")
        )
        result = self.confirmed("sign_document", {"player_id": self.kid.id, "document": "waiver"})

        self.assertFalse(result["isError"], result)
        sub.refresh_from_db()
        self.assertEqual(self.user, sub.waiver_signed_by)

    def test_a_guardian_cannot_sign_for_an_adult_ward(self) -> None:
        for document in ("waiver", "coc"):
            with self.subTest(document):
                self.subscribe(self.adult_ward) if document == "waiver" else None
                result = self.ask(self.adult_ward, document)

                self.assertTrue(result["isError"])
                self.assertIn("Cal Rao can", result["structuredContent"]["message"])

    def test_hubs_refusal_is_surfaced_when_the_precheck_lets_it_through(self) -> None:
        self.subscribe(self.kid)
        make_token(self.kid_user, "ktok", scope="hub:read hub:write")
        args = {"player_id": self.kid.id, "document": "waiver"}

        with mock.patch("server.mcp.tools.profile._refusal", return_value=None):
            result = self.confirmed("sign_document", args, bearer="ktok")

        self.assertTrue(result["isError"])
        self.assertEqual(
            "Waiver can only signed by a guardian", result["structuredContent"]["message"]
        )

    def test_a_minors_own_login_cannot_sign(self) -> None:
        self.subscribe(self.kid)
        make_token(self.kid_user, "ktok", scope="hub:read hub:write")

        result = self.call(
            "sign_document", {"player_id": self.kid.id, "document": "waiver"}, bearer="ktok"
        )

        self.assertTrue(result["isError"])
        self.assertIn("guardian", result["structuredContent"]["message"])

    def test_a_minor_with_no_guardian_is_refused_before_asking(self) -> None:
        orphan = self.make_player(
            User.objects.create(username="o@x.com", first_name="Ola"), "2014-01-01"
        )
        self.subscribe(orphan)
        make_token(orphan.user, "otok", scope="hub:read hub:write")

        result = self.call("sign_document", {"player_id": orphan.id, "document": "waiver"}, "otok")

        self.assertTrue(result["isError"])
        self.assertEqual(
            "Waiver can only signed by a guardian", result["structuredContent"]["message"]
        )

    def test_a_stranger_is_denied(self) -> None:
        other = self.make_player(User.objects.create(username="s@x.com", first_name="Sam"))
        self.subscribe(other)

        result = self.ask(other)

        self.assertTrue(result["isError"])
        self.assertIn("Not allowed", result["structuredContent"]["message"])

    def test_no_membership_points_to_buying_one(self) -> None:
        result = self.ask(self.me)

        self.assertTrue(result["isError"])
        self.assertIn("membership", result["structuredContent"]["message"])
        self.assertEqual("get_membership_options", result["structuredContent"]["hint"].split()[0])

    def test_the_code_of_conduct_is_signed_the_same_way(self) -> None:
        sub = self.subscribe(self.me)

        result = self.confirmed("sign_document", {"player_id": self.me.id, "document": "coc"})

        self.assertFalse(result["isError"], result)
        sub.refresh_from_db()
        self.assertTrue(sub.coc_agreed)

    def test_an_already_signed_document_is_not_signed_again(self) -> None:
        self.subscribe(self.me, waiver_valid=True, waiver_signed_by=self.user)

        result = self.ask(self.me)

        self.assertFalse(result["isError"])
        self.assertTrue(result["structuredContent"]["done"])
        self.assertNotIn("needs_confirmation", result["structuredContent"])

    def test_long_text_gets_key_points_and_a_link(self) -> None:
        self.subscribe(self.me)

        asked = self.ask(self.me)["structuredContent"]["needs_confirmation"]

        self.assertIn(f"{HUB}/waiver/{self.me.id}", asked)
        self.assertLess(len(asked), 3000)
        self.assertNotIn("indemnify, defend", asked)

    def test_the_fallback_result_carries_the_full_text(self) -> None:
        self.subscribe(self.kid)

        asked = self.ask(self.kid)["structuredContent"]

        self.assertIn("on behalf of my son/daughter/ward", asked["full_text"])
        self.assertIn("Wren Rao", asked["full_text"])
        self.assertNotIn("{", asked["full_text"])

    def test_the_adult_and_minor_texts_differ(self) -> None:
        self.subscribe(self.me)
        self.subscribe(self.kid)

        adult = self.ask(self.me)["structuredContent"]["full_text"]
        minor = self.ask(self.kid)["structuredContent"]["full_text"]

        self.assertNotIn("son/daughter/ward", adult)
        self.assertIn("parent or legal guardian", minor)

    def test_the_confirmation_is_bound_to_the_text_shown(self) -> None:
        self.subscribe(self.me)
        asked = self.ask(self.me)["structuredContent"]
        edited = DOCUMENTS["waiver_adult"] + "\nAn extra clause."

        with mock.patch.dict(DOCUMENTS, {"waiver_adult": edited}):
            result = self.call(
                "sign_document",
                {
                    "player_id": self.me.id,
                    "document": "waiver",
                    "confirmation": asked["confirmation"],
                },
            )

        data = result["structuredContent"]
        self.assertFalse(data["done"])
        self.assertTrue(data["needs_confirmation"].startswith("Something changed"))
        self.assertFalse(
            Subscription.objects.filter(player=self.me, waiver_signed_at__isnull=False).exists()
        )


def squash(text: str) -> str:
    text = text.replace('{" "}', " ")
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text)


class TestDocumentTexts(SimpleTestCase):
    def test_the_code_of_conduct_equals_the_frontend_file(self) -> None:
        mine = Path(__file__).resolve().parents[1] / "mcp" / "documents" / "code_of_conduct.md"

        self.assertEqual(
            (FRONTEND / "markdowns" / "code-of-conduct.md").read_bytes(), mine.read_bytes()
        )

    def test_each_waiver_sentence_still_appears_in_the_frontend(self) -> None:
        source = squash((FRONTEND / "components" / "Waiver.js").read_text())
        for name in ("waiver_adult", "waiver_minor"):
            for line in DOCUMENTS[name].splitlines():
                if not line or line.startswith(("#", "Validity")):
                    continue
                for raw in re.split(r"\{\w+\}", re.sub(r"^\d+\.\s+", "", line)):
                    part = squash(raw).strip()
                    if len(part) > MIN_PART:
                        with self.subTest(name=name, part=part[:50]):
                            self.assertIn(part, source)

    def test_each_frontend_paragraph_still_appears_in_the_waiver_texts(self) -> None:
        source = (FRONTEND / "components" / "Waiver.js").read_text()
        texts = {
            name: squash(re.sub(r"\{\w+\}", " ", DOCUMENTS[name]))
            for name in ("waiver_adult", "waiver_minor")
        }
        paragraphs = re.findall(r"<(?:li|p|span)[^>]*>([^<]*?)</(?:li|p|span)>", source)
        found = 0
        for raw in paragraphs:
            if "{" in raw and "displayDate" not in raw and "props." not in raw:
                continue
            for part in re.split(r"\{[^}]*\}", raw):
                text = squash(part).strip()
                if len(text) > MIN_PART and "There is no active" not in text:
                    found += 1
                    with self.subTest(part=text[:50]):
                        self.assertTrue(any(squash(text) in t for t in texts.values()))
        self.assertGreater(found, 20)

    def test_only_known_placeholders_remain(self) -> None:
        for name in ("waiver_adult", "waiver_minor"):
            found = set(re.findall(r"\{(\w+)\}", DOCUMENTS[name]))
            self.assertLessEqual(found, {"player_name", "start_date", "end_date"})

import datetime
import json
from typing import Any
from unittest import mock

from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, override_settings
from django.test.client import MULTIPART_CONTENT
from django.utils import timezone

import server.mcp.tools  # noqa: F401
from server.core.models import CollegeId, Guardianship, Player, Team, User
from server.mcp import upload
from server.mcp.auth import TokenInfo
from server.mcp.models import McpNonce
from server.mcp.registry import TOOLS, ToolContext
from server.tests.base import ApiBaseTestCase, wfdf_certificate_pdf
from server.ticket.models import Ticket
from server.utils import today


def image(name: str = "f.png", size: int = 3) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"x" * size, content_type="image/png")


def pdf(content: bytes = b"%PDF-1.4") -> SimpleUploadedFile:
    return SimpleUploadedFile("c.pdf", content, content_type="application/pdf")


class UploadTestCase(ApiBaseTestCase):
    def ctx(self, user: User | None = None) -> ToolContext:
        user = user or self.user
        return ToolContext(
            user=user,
            token=TokenInfo(user, frozenset({"hub:write"}), "client"),
            modern=True,
            client_capabilities={},
            input_responses=None,
            request_state=None,
            tool_name="create_upload_link",
            outer=RequestFactory().post("/mcp"),
        )

    def ask(self, args: dict[str, Any]) -> Any:
        return TOOLS["create_upload_link"].handler(self.ctx(), args)

    def confirmed(self, args: dict[str, Any]) -> Any:
        asked = self.ask(args).data
        self.assertFalse(asked["done"], asked)
        return self.ask({**args, "confirmation": asked["confirmation"]})

    def link(self, **args: Any) -> str:
        result = self.confirmed(args)
        self.assertFalse(result.is_error, result.data)
        return str(result.data["upload_url"]).split("/mcp/upload/")[1]

    def send(self, token: str, **files: SimpleUploadedFile) -> Any:
        return self.client.post(f"/mcp/upload/{token}", data=files, content_type=MULTIPART_CONTENT)


class TestCreateUploadLink(UploadTestCase):
    def test_the_link_names_files_and_a_curl_command(self) -> None:
        result = self.confirmed(
            {
                "kind": "college_id",
                "player_id": self.player.pk,
                "details": {"expiry": "2030-01-01"},
            },
        )

        data = result.data
        self.assertEqual(900, data["expires_in_seconds"])
        self.assertEqual(["card_front", "card_back"], data["files"])
        self.assertTrue(data["curl"].startswith("curl -F card_front=@/path/to/card_front "))
        self.assertIn(data["upload_url"], data["curl"])

    def test_nothing_is_minted_until_the_user_says_yes(self) -> None:
        cases: list[tuple[dict[str, Any], str]] = [
            ({"kind": "accreditation", "player_id": self.player.pk}, "WFDF certificate for"),
            (
                {
                    "kind": "ticket_attachment",
                    "ticket_id": Ticket.objects.create(
                        title="T", description="-", created_by=self.user
                    ).pk,
                    "details": {"message": "see attached"},
                },
                "'see attached'; this emails",
            ),
            (
                {
                    "kind": "new_team",
                    "details": {
                        "name": "Wolves",
                        "category": "Club",
                        "state_ut": "KA",
                        "city": "BLR",
                    },
                },
                "Create the team Wolves (Club, BLR) with the uploaded logo",
            ),
            ({"kind": "profile_pic"}, "profile picture"),
        ]
        for args, words in cases:
            with self.subTest(kind=args["kind"]):
                data = self.ask(args).data

                self.assertNotIn("upload_url", data)
                self.assertIn(words, data["needs_confirmation"])

    def test_a_confirmation_is_bound_to_the_kind_and_target(self) -> None:
        asked = self.ask({"kind": "accreditation", "player_id": self.player.pk}).data

        swapped = self.ask(
            {
                "kind": "college_id",
                "player_id": self.player.pk,
                "details": {"expiry": "2030-01-01"},
                "confirmation": asked["confirmation"],
            }
        )

        self.assertNotIn("upload_url", swapped.data)

    def test_refuses_another_persons_player(self) -> None:
        other = User.objects.create(username="o@x.com", email="o@x.com")
        stranger = Player.objects.create(user=other, date_of_birth="1995-05-05", gender="F")

        result = TOOLS["create_upload_link"].handler(
            self.ctx(), {"kind": "accreditation", "player_id": stranger.pk}
        )

        self.assertTrue(result.is_error)
        self.assertIn("Not allowed", result.data["message"])

    def test_refuses_a_ticket_the_user_cannot_see(self) -> None:
        other = User.objects.create(username="o@x.com", email="o@x.com")
        ticket = Ticket.objects.create(
            title="T", description="-", created_by=other, is_private=True
        )

        result = TOOLS["create_upload_link"].handler(
            self.ctx(),
            {"kind": "ticket_attachment", "ticket_id": ticket.pk, "details": {"message": "hi"}},
        )

        self.assertTrue(result.is_error)

    def test_refuses_a_logo_for_a_team_the_user_does_not_administer(self) -> None:
        result = TOOLS["create_upload_link"].handler(
            self.ctx(), {"kind": "team_logo", "team_id": self.teams[0].pk}
        )

        self.assertTrue(result.is_error)
        self.assertIn("Not allowed", result.data["message"])

    def test_a_guardian_may_make_a_link_for_a_ward(self) -> None:
        ward = Player.objects.create(
            user=User.objects.create(username="w@x.com", email="w@x.com"),
            date_of_birth="2015-05-05",
            gender="F",
        )
        Guardianship.objects.create(user=self.user, player=ward)

        self.link(kind="accreditation", player_id=ward.pk)

    def test_long_details_are_refused(self) -> None:
        ticket = Ticket.objects.create(title="T", description="-", created_by=self.user)
        cases: list[dict[str, Any]] = [
            {
                "kind": "ticket_attachment",
                "ticket_id": ticket.pk,
                "details": {"message": "x" * 1001},
            },
            {
                "kind": "new_team",
                "details": {"name": "n", "category": "Club", "state_ut": "KA", "city": "c" * 31},
            },
        ]
        for args in cases:
            with self.subTest(kind=args["kind"]):
                result = TOOLS["create_upload_link"].handler(self.ctx(), args)

                self.assertTrue(result.is_error)
                self.assertIn("at most", result.data["message"])

    def test_missing_details_are_named(self) -> None:
        result = TOOLS["create_upload_link"].handler(
            self.ctx(), {"kind": "college_id", "player_id": self.player.pk}
        )

        self.assertEqual("details.expiry is required for college_id.", result.data["message"])

    def test_a_college_id_expiry_must_be_a_date(self) -> None:
        for expiry in ("May 27", "20270531", "2027-02-30"):
            with self.subTest(expiry=expiry):
                result = TOOLS["create_upload_link"].handler(
                    self.ctx(),
                    {
                        "kind": "college_id",
                        "player_id": self.player.pk,
                        "details": {"expiry": expiry},
                    },
                )

                self.assertIn("must be a date", result.data["message"])


class TestUploadKinds(UploadTestCase):
    def test_accreditation(self) -> None:
        token = self.link(kind="accreditation", player_id=self.player.pk)

        response = self.send(token, certificate=pdf(wfdf_certificate_pdf()))

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            {"ok": True, "message": "Accreditation saved.", "player_id": self.player.pk},
            response.json(),
        )
        self.player.refresh_from_db()
        self.assertTrue(self.player.accreditation.is_valid)

    def test_college_id(self) -> None:
        expiry = str(today() + datetime.timedelta(days=100))
        token = self.link(kind="college_id", player_id=self.player.pk, details={"expiry": expiry})

        response = self.send(token, card_front=image("f.png"), card_back=image("b.png"))

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(expiry, str(CollegeId.objects.get(player=self.player).expiry))

    def test_vaccination(self) -> None:
        token = self.link(
            kind="vaccination", player_id=self.player.pk, details={"vaccine_name": "CVXN"}
        )

        response = self.send(token, certificate=pdf())

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("CVXN", Player.objects.get(pk=self.player.pk).vaccination.name)

    def test_profile_pic(self) -> None:
        token = self.link(kind="profile_pic")

        with mock.patch(
            "cloudinary.uploader.upload", return_value={"secure_url": "https://x.org/me.png"}
        ):
            response = self.send(token, profile_pic=image())

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            "https://x.org/me.png", Player.objects.get(pk=self.player.pk).profile_pic_url
        )

    def test_ticket_attachment(self) -> None:
        ticket = Ticket.objects.create(title="T", description="-", created_by=self.user)
        token = self.link(
            kind="ticket_attachment", ticket_id=ticket.pk, details={"message": "See attached"}
        )

        with mock.patch(
            "cloudinary.uploader.upload", return_value={"secure_url": "https://x.org/a.pdf"}
        ):
            response = self.send(token, attachment=pdf())

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(ticket.pk, response.json()["ticket_id"])
        message = ticket.messages.get()
        self.assertEqual(
            ("See attached", "https://x.org/a.pdf"), (message.message, message.attachment)
        )

    def test_team_logo(self) -> None:
        team = Team.objects.create(name="Mine", category="Club")
        team.admins.add(self.user)
        token = self.link(kind="team_logo", team_id=team.pk)

        response = self.send(token, image=image("logo.png"))

        self.assertEqual(200, response.status_code, response.content)
        team.refresh_from_db()
        self.assertIn("logo", team.image.name)

    def test_new_team(self) -> None:
        details = {"name": "Fresh", "category": "Club", "state_ut": "KA", "city": "Bengaluru"}
        token = self.link(kind="new_team", details=details)

        response = self.send(token, image=image("logo.png"))

        self.assertEqual(200, response.status_code, response.content)
        team = Team.objects.get(name="Fresh")
        self.assertEqual(
            {"team_id": team.pk, "team_slug": team.slug},
            {k: response.json()[k] for k in ("team_id", "team_slug")},
        )
        self.assertIn(self.user, team.admins.all())


class TestUploadRefusals(UploadTestCase):
    def test_a_second_use_is_gone(self) -> None:
        token = self.link(kind="profile_pic")
        with mock.patch(
            "cloudinary.uploader.upload", return_value={"secure_url": "https://x.org/me.png"}
        ):
            self.send(token, profile_pic=image())
            response = self.send(token, profile_pic=image())

        self.assertEqual(410, response.status_code)

    def test_an_expired_link_is_gone(self) -> None:
        token = self.link(kind="profile_pic")
        spent = McpNonce.objects.count()

        with mock.patch("django.core.signing.time.time", return_value=9_999_999_999):
            response = self.send(token, profile_pic=image())

        self.assertEqual(410, response.status_code)
        self.assertEqual(spent, McpNonce.objects.count())

    def test_a_deactivated_or_deleted_user_is_refused_without_a_500(self) -> None:
        token = self.link(kind="profile_pic")
        spent = McpNonce.objects.count()
        self.user.is_active = False
        self.user.save()

        post = self.send(token, profile_pic=image())
        get = self.client.get(f"/mcp/upload/{token}", HTTP_ACCEPT="application/json")
        User.objects.filter(pk=self.user.pk).delete()
        deleted = self.send(token, profile_pic=image())

        self.assertEqual([410, 410, 410], [post.status_code, get.status_code, deleted.status_code])
        self.assertEqual(spent, McpNonce.objects.count())

    def test_a_bad_token_is_404(self) -> None:
        self.assertEqual(404, self.send("nonsense", profile_pic=image()).status_code)

    def test_wrong_field_name_is_refused_and_nothing_burned(self) -> None:
        token = self.link(kind="accreditation", player_id=self.player.pk)
        spent = McpNonce.objects.count()

        response = self.send(token, file=pdf())

        self.assertEqual(400, response.status_code)
        self.assertEqual(spent, McpNonce.objects.count())

    def test_oversize_file_is_refused_before_dispatch(self) -> None:
        token = self.link(kind="profile_pic")

        with mock.patch("server.mcp.upload.call_api") as call:
            response = self.send(token, profile_pic=image(size=10 * 1024 * 1024 + 1))

        self.assertEqual(413, response.status_code)
        call.assert_not_called()

    def test_a_route_error_does_not_burn_the_link(self) -> None:
        token = self.link(kind="accreditation", player_id=self.player.pk)

        first = self.send(token, certificate=pdf(b"not a certificate"))
        second = self.send(token, certificate=pdf(wfdf_certificate_pdf()))

        self.assertEqual(400, first.status_code)
        self.assertFalse(first.json()["ok"])
        self.assertEqual(200, second.status_code, second.content)

    def test_the_route_rechecks_permission(self) -> None:
        team = Team.objects.create(name="Mine", category="Club")
        team.admins.add(self.user)
        token = self.link(kind="team_logo", team_id=team.pk)
        team.admins.clear()

        response = self.send(token, image=image())

        self.assertEqual(400, response.status_code)
        self.assertIn("not an admin", response.json()["message"])


class TestUploadPage(UploadTestCase):
    def describe(self, token: str) -> Any:
        return self.client.get(f"/mcp/upload/{token}", HTTP_ACCEPT="application/json")

    def test_a_browser_is_sent_to_the_app_page(self) -> None:
        token = self.link(kind="profile_pic")

        response = self.client.get(f"/mcp/upload/{token}")

        self.assertRedirects(response, f"/upload/{token}", fetch_redirect_response=False)

    def test_the_owner_gets_the_fields_to_fill(self) -> None:
        token = self.link(
            kind="college_id", player_id=self.player.pk, details={"expiry": "2030-01-01"}
        )
        self.client.force_login(self.user)

        body = self.describe(token).json()

        self.assertTrue(body["mine"])
        self.assertEqual("college ID", body["what"])
        self.assertEqual(["card_front", "card_back"], [f["name"] for f in body["fields"]])
        self.assertEqual("An image", body["fields"][0]["hint"])
        self.assertEqual(10 * 1024 * 1024, body["max_bytes"])

    def test_anyone_else_learns_only_whose_link_it_is(self) -> None:
        token = self.link(kind="profile_pic")

        for login in (False, True):
            with self.subTest(login=login):
                if login:
                    self.client.force_login(
                        User.objects.create(username="o@x.com", email="o@x.com")
                    )
                response = self.describe(token)

                self.assertFalse(response.json()["mine"])
                self.assertEqual(
                    self.user.get_full_name() or "another Hub account",
                    response.json()["sign_in_as"],
                )
                self.assertNotContains(response, "@foo.com")

    def test_a_bad_link_is_404_an_expired_or_used_one_410(self) -> None:
        self.assertEqual(404, self.describe("nonsense").status_code)
        token = self.link(kind="profile_pic")
        with mock.patch("django.core.signing.time.time", return_value=9_999_999_999):
            self.assertEqual(410, self.describe(token).status_code)
        nonce = signing.loads(token, salt=upload.SALT)["n"]
        McpNonce.objects.create(key=nonce, expires_at=timezone.now())
        used = self.describe(token)
        self.assertEqual(410, used.status_code)
        self.assertIn("already used", used.json()["message"])

    def test_disabled_server_hides_the_link(self) -> None:
        token = self.link(kind="profile_pic")
        with override_settings(MCP_ENABLED=False):
            self.assertEqual(404, self.describe(token).status_code)


class TestRouteLimits(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def post(self, path: str, part: str, data: dict[str, Any], **files: SimpleUploadedFile) -> Any:
        return self.client.post(
            path, data={part: json.dumps(data), **files}, content_type=MULTIPART_CONTENT
        )

    def test_vaccination_certificate_must_be_image_or_pdf_under_10mb(self) -> None:
        data = {"is_vaccinated": True, "name": "CVXN", "player_id": self.player.pk}
        bad = SimpleUploadedFile("c.exe", b"x", content_type="application/x-msdownload")
        big = SimpleUploadedFile(
            "c.pdf", b"x" * (10 * 1024 * 1024 + 1), content_type="application/pdf"
        )

        self.assertEqual(
            400, self.post("/api/vaccination", "vaccination", data, certificate=bad).status_code
        )
        self.assertEqual(
            400, self.post("/api/vaccination", "vaccination", data, certificate=big).status_code
        )
        self.assertEqual(
            200, self.post("/api/vaccination", "vaccination", data, certificate=image()).status_code
        )

    def test_college_id_images_must_be_images_under_10mb(self) -> None:
        data = {"player_id": self.player.pk, "expiry": str(today() + datetime.timedelta(days=9))}

        for bad in (pdf(), image(size=10 * 1024 * 1024 + 1)):
            response = self.post(
                "/api/college-id", "college_id", data, card_front=bad, card_back=image()
            )
            self.assertEqual(400, response.status_code)
        self.assertFalse(CollegeId.objects.exists())

    def test_accreditation_must_be_a_pdf_under_10mb(self) -> None:
        data = {"player_id": self.player.pk}

        for bad in (image(), pdf(b"x" * (10 * 1024 * 1024 + 1))):
            response = self.post("/api/accreditation", "accreditation", data, certificate=bad)
            self.assertEqual(400, response.status_code)


class TestTeamLogoLimits(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        self.team = Team.objects.create(name="Mine", category="Club")
        self.team.admins.add(self.user)

    def post(self, path: str, part: str, data: dict[str, Any], logo: SimpleUploadedFile) -> Any:
        return self.client.post(
            path, data={part: json.dumps(data), "image": logo}, content_type=MULTIPART_CONTENT
        )

    def bad_logos(self) -> list[SimpleUploadedFile]:
        return [pdf(), image(size=10 * 1024 * 1024 + 1)]

    def test_edit_refuses_a_bad_logo(self) -> None:
        for bad in self.bad_logos():
            response = self.post("/api/teams/edit", "team_details", {"id": str(self.team.pk)}, bad)
            self.assertEqual(400, response.status_code)

    def test_create_refuses_a_bad_logo(self) -> None:
        details = {"name": "Fresh", "category": "Club", "state_ut": "KA", "city": "Bengaluru"}
        for bad in self.bad_logos():
            self.assertEqual(400, self.post("/api/teams", "team_details", details, bad).status_code)
        self.assertFalse(Team.objects.filter(name="Fresh").exists())

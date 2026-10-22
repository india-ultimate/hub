from typing import Any
from unittest import mock

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404, HttpRequest, HttpResponse, StreamingHttpResponse
from django.test import RequestFactory, override_settings

from server.core.models import Player, User
from server.mcp.auth import TokenInfo
from server.mcp.dispatch import ApiResponse, call_api
from server.mcp.registry import ToolContext
from server.tests.base import ApiBaseTestCase


class TestCallApi(ApiBaseTestCase):
    def ctx(self, user: User | None = None) -> ToolContext:
        user = user or self.user
        return ToolContext(
            user=user,
            token=TokenInfo(user, frozenset({"hub:read"}), "client"),
            modern=True,
            client_capabilities={},
            input_responses=None,
            request_state=None,
            tool_name="test",
            outer=RequestFactory().post("/mcp"),
        )

    def stranger(self) -> Player:
        user = User.objects.create(username="s@x.com", email="s@x.com")
        return Player.objects.create(user=user, date_of_birth="1995-05-05", gender="F")

    def test_get_me_is_the_token_user(self) -> None:
        response = call_api(self.ctx(), "GET", "/api/me")

        self.assertEqual(200, response.status)
        self.assertTrue(response.ok)
        self.assertEqual("John Williamson", response.data["full_name"])

    def test_hub_permission_check_applies(self) -> None:
        response = call_api(self.ctx(), "GET", f"/api/players/{self.stranger().pk}")

        self.assertEqual(403, response.status)
        self.assertEqual("You can't see this player's details", response.data["message"])

    def test_post_json_body(self) -> None:
        response = call_api(
            self.ctx(),
            "POST",
            "/api/ticket/",
            body={"title": "Help", "description": "Please"},
        )

        self.assertEqual(201, response.status)

    def test_staff_route_refuses_non_staff(self) -> None:
        self.assertEqual(403, call_api(self.ctx(), "GET", "/api/players").status)

    def test_multipart_file_reaches_the_handler(self) -> None:
        upload = SimpleUploadedFile("me.png", b"png", content_type="image/png")
        with mock.patch(
            "cloudinary.uploader.upload", return_value={"secure_url": "https://x.org/me.png"}
        ) as cloudinary:
            response = call_api(
                self.ctx(), "POST", "/api/profile-pic", files={"profile_pic": upload}
            )

        self.assertEqual(200, response.status, response.data)
        cloudinary.assert_called_once()
        self.player.refresh_from_db()
        self.assertEqual("https://x.org/me.png", self.player.profile_pic_url)

    def test_unknown_route_is_404(self) -> None:
        self.assertEqual(404, call_api(self.ctx(), "GET", "/api/nope").status)

    def test_only_api_paths_are_allowed(self) -> None:
        for path in ("/api/../admin/", "/admin/", "api/me", "/api/me?x=1", "/apiary"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                call_api(self.ctx(), "GET", path)

    @override_settings(ALLOWED_HOSTS=["hub.example"])
    def test_sub_request_carries_the_outer_host_and_scheme(self) -> None:
        ctx = self.ctx()
        ctx.outer = RequestFactory().post("/mcp", secure=True, HTTP_HOST="hub.example")
        seen: dict[str, str] = {}

        def view(request: HttpRequest) -> HttpResponse:
            seen["url"] = request.build_absolute_uri("/x")
            return HttpResponse("{}")

        with mock.patch(
            "server.mcp.dispatch.resolve", return_value=mock.Mock(func=view, args=(), kwargs={})
        ):
            call_api(ctx, "GET", "/api/anything")

        self.assertEqual("https://hub.example/x", seen["url"])

    def dispatch_raising(self, error: Exception) -> ApiResponse:
        def view(request: HttpRequest) -> HttpResponse:
            raise error

        with mock.patch(
            "server.mcp.dispatch.resolve", return_value=mock.Mock(func=view, args=(), kwargs={})
        ):
            return call_api(self.ctx(), "GET", "/api/anything")

    def test_http404_becomes_a_404_response(self) -> None:
        response = self.dispatch_raising(Http404("No such thing"))

        self.assertEqual((404, {"message": "No such thing"}), (response.status, response.data))

    def test_permission_denied_becomes_a_403_response(self) -> None:
        response = self.dispatch_raising(PermissionDenied())

        self.assertEqual((403, {"message": "Permission denied"}), (response.status, response.data))

    def test_streaming_response_has_no_data(self) -> None:
        with mock.patch(
            "server.mcp.dispatch.resolve",
            return_value=mock.Mock(
                func=lambda request: StreamingHttpResponse([b"x"]), args=(), kwargs={}
            ),
        ):
            response = call_api(self.ctx(), "GET", "/api/anything")

        self.assertEqual((200, None), (response.status, response.data))

    def test_message_is_hubs_or_a_fallback(self) -> None:
        self.assertEqual("Nope", ApiResponse(400, {"message": "Nope"}).message)
        odd: list[Any] = [None, [], {"detail": "x"}, {"message": 3}]
        for data in odd:
            self.assertEqual("Hub answered 500", ApiResponse(500, data).message)

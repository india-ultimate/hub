"""Custom middleware for the hub."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

AUTH_HINT_COOKIE = "hub_auth"


class AuthHintCookieMiddleware:
    """Mirror authentication state into a cookie the frontend can read.

    The session cookie is HttpOnly, so the SPA could not tell it was signed out
    without asking and taking a 401 -- 5,919 of them in the 24h to 2026-08-28. This
    lets it skip the call. A hint only: endpoints still authenticate from the
    session, and forging it earns nothing but a 401.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # Reading request.user forces a session read, so only look when a session
        # cookie is in play -- anonymous requests then cost no extra query. The
        # outbound check covers login, which has no inbound cookie yet.
        touches_session = (
            settings.SESSION_COOKIE_NAME in request.COOKIES
            or settings.SESSION_COOKIE_NAME in response.cookies
        )
        if touches_session:
            user = getattr(request, "user", None)
            is_authenticated = bool(user is not None and user.is_authenticated)
        else:
            is_authenticated = False

        if is_authenticated:
            # Reset on every response so it cannot expire under a live session.
            response.set_cookie(
                AUTH_HINT_COOKIE,
                "1",
                max_age=settings.SESSION_COOKIE_AGE,
                secure=settings.SESSION_COOKIE_SECURE,
                httponly=False,  # the point: the frontend has to read it
                samesite="Lax",
            )
        elif AUTH_HINT_COOKIE in request.COOKIES:
            response.delete_cookie(AUTH_HINT_COOKIE, samesite="Lax")

        return response

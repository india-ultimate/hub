from django.conf import settings
from django.shortcuts import redirect
from django.urls import URLPattern, URLResolver, path  # noqa: F401
from django.views.decorators.csrf import ensure_csrf_cookie

from . import views
from .api import api

urlpatterns = [path("api/", api.urls)]  # type: list[URLPattern | URLResolver]

if settings.DEBUG:
    url = f"http://localhost:{settings.WEBPACK_SERVER_PORT}"
    urlpatterns.append(path("", ensure_csrf_cookie(lambda req: redirect(url))))

else:
    urlpatterns.append(path("", views.home, name="home"))

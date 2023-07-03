from django.conf import settings
from django.shortcuts import redirect
from django.urls import path
from django.views.decorators.csrf import ensure_csrf_cookie

from . import views
from .api import api

urlpatterns = [path("api/", api.urls)]

if settings.DEBUG:
    urlpatterns.append(path("", ensure_csrf_cookie(lambda req: redirect("http://localhost:3000"))))

else:
    urlpatterns.append(path("", views.home, name="home"))

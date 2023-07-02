from django.conf import settings
from django.shortcuts import redirect
from django.urls import path

from .api import api

urlpatterns = [path("api/", api.urls)]

if settings.DEBUG:
    urlpatterns.append(path("", lambda x: redirect("http://localhost:3000")))
else:
    raise RuntimeError("FIXME: Figure out deployment of the app!")

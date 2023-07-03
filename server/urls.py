from django.conf import settings
from django.shortcuts import redirect
from django.urls import path

urlpatterns = []

if settings.DEBUG:
    urlpatterns.append(path("", lambda x: redirect("http://localhost:3000")))
else:
    raise RuntimeError("FIXME: Figure out deployment of the app!")

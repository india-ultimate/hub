from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("registration", views.registration_view, name="registration"),
    path(
        "registration_success/<str:membership_number>/",
        views.registration_success_view,
        name="registration_success",
    ),
]

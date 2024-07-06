from django.contrib import admin

from server.models import Event, Player, Team, Tournament, User


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin[Player]):
    search_fields = ["user__first_name", "user__last_name", "user__username"]


@admin.register(User)
class UserAdmin(admin.ModelAdmin[User]):
    search_fields = ["first_name", "last_name", "username"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin[Team]):
    search_fields = ["name"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin[Event]):
    search_fields = ["title"]


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin[Tournament]):
    pass

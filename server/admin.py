from django.contrib import admin

from server.models import (
    Event,
    Match,
    Membership,
    Player,
    Pool,
    Team,
    Tournament,
    TournamentField,
    User,
)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin[Player]):
    search_fields = ["user__first_name", "user__last_name", "user__username"]
    list_display = ["get_name", "get_email"]

    @admin.display(description="Name", ordering="user__first_name")
    def get_name(self, obj: Player) -> str:
        return obj.user.first_name + " " + obj.user.last_name

    @admin.display(description="Email", ordering="user__username")
    def get_email(self, obj: Player) -> str:
        return obj.user.username


@admin.register(User)
class UserAdmin(admin.ModelAdmin[User]):
    search_fields = ["first_name", "last_name", "username"]
    list_display = ["first_name", "last_name", "username"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin[Team]):
    search_fields = ["name"]
    list_display = ["name"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin[Event]):
    search_fields = ["title"]
    list_display = ["title"]


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin[Tournament]):
    search_fields = ["event__title"]
    list_display = ["get_name"]

    @admin.display(description="Name", ordering="event__title")
    def get_name(self, obj: Tournament) -> str:
        return obj.event.title


@admin.register(TournamentField)
class TournamentFieldAdmin(admin.ModelAdmin[TournamentField]):
    search_fields = ["tournament__event__title"]
    list_display = ["get_name", "name"]

    @admin.display(description="Tournament Name", ordering="tournament__event__title")
    def get_name(self, obj: TournamentField) -> str:
        return obj.tournament.event.title


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin[Pool]):
    search_fields = ["tournament__event__title"]
    list_display = ["get_name", "name"]

    @admin.display(description="Tournament Name", ordering="tournament__event__title")
    def get_name(self, obj: Pool) -> str:
        return obj.tournament.event.title


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin[Match]):
    search_fields = ["tournament__event__title"]
    list_display = ["get_name", "name"]

    @admin.display(description="Tournament Name", ordering="tournament__event__title")
    def get_name(self, obj: Match) -> str:
        return obj.tournament.event.title


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin[Membership]):
    search_fields = ["player__user__first_name"]
    list_display = [
        "get_name",
        "membership_number",
        "is_annual",
        "start_date",
        "end_date",
        "is_active",
    ]

    @admin.display(description="Player Name", ordering="player__user__first_name")
    def get_name(self, obj: Membership) -> str:
        return obj.player.user.first_name

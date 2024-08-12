import csv

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse

from server.core.models import (
    Player,
    Team,
    User,
)
from server.membership.models import (
    ManualTransaction,
    Membership,
    PhonePeTransaction,
    RazorpayTransaction,
)
from server.season.models import Season
from server.tournament.models import (
    Event,
    Match,
    Pool,
    Tournament,
    TournamentField,
)


@admin.action(description="Export Selected")
def export_as_csv(
    self: admin.ModelAdmin[
        Membership | RazorpayTransaction | PhonePeTransaction | ManualTransaction
    ],
    request: HttpRequest,
    queryset: QuerySet[Membership | RazorpayTransaction | PhonePeTransaction | ManualTransaction],
) -> HttpResponse:
    meta = self.model._meta
    field_names = [field.name for field in meta.fields]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename={meta}.csv"
    writer = csv.writer(response)

    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])

    return response


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
class UserAdmin(DjangoUserAdmin):
    search_fields = ["first_name", "last_name", "username"]
    list_display = [
        "first_name",
        "last_name",
        "username",
        "is_staff",
        "is_superuser",
        "is_tournament_admin",
    ]
    list_filter = ["is_staff", "is_superuser", "is_tournament_admin"]
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (("Personal info"), {"fields": ("first_name", "last_name", "email", "phone")}),
        (
            ("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                    "is_tournament_admin",
                ),
            },
        ),
        (("Important dates"), {"fields": ("last_login", "date_joined")}),
    )


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
    actions = [export_as_csv]

    @admin.display(description="Player Name", ordering="player__user__first_name")
    def get_name(self, obj: Membership) -> str:
        return obj.player.user.first_name


@admin.register(RazorpayTransaction)
class RazorpayTransactionAdmin(admin.ModelAdmin[RazorpayTransaction]):
    search_fields = ["user__first_name"]
    list_display = ["get_name", "order_id", "payment_id", "amount", "payment_date", "status"]
    actions = [export_as_csv]

    @admin.display(description="User Name", ordering="user__first_name")
    def get_name(self, obj: RazorpayTransaction) -> str:
        return obj.user.first_name


@admin.register(PhonePeTransaction)
class PhonePeTransactionAdmin(admin.ModelAdmin[PhonePeTransaction]):
    search_fields = ["user__first_name"]
    list_display = ["get_name", "transaction_id", "amount", "transaction_date", "status"]
    actions = [export_as_csv]

    @admin.display(description="User Name", ordering="user__first_name")
    def get_name(self, obj: PhonePeTransaction) -> str:
        return obj.user.first_name


@admin.register(ManualTransaction)
class ManualTransactionAdmin(admin.ModelAdmin[ManualTransaction]):
    search_fields = ["user__first_name"]
    list_display = ["get_name", "transaction_id", "amount", "payment_date"]
    actions = [export_as_csv]

    @admin.display(description="User Name", ordering="user__first_name")
    def get_name(self, obj: ManualTransaction) -> str:
        return obj.user.first_name


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin[Season]):
    search_fields = ["name"]
    list_display = ["name"]

import csv
from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import CharField, Q, QuerySet, Sum, Value
from django.db.models.functions import Concat
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from server.core.models import (
    Accreditation,
    Guardianship,
    Player,
    Team,
    User,
)
from server.membership.models import Membership
from server.season.models import Season
from server.series.models import Series, SeriesRegistration, SeriesRosterInvitation
from server.tournament.models import (
    Bracket,
    CrossPool,
    Event,
    Match,
    MatchEvent,
    MatchStats,
    Pool,
    PositionPool,
    Registration,
    Tournament,
    TournamentField,
)
from server.transaction.models import ManualTransaction, PhonePeTransaction, RazorpayTransaction


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
    search_fields = ["user__first_name", "user__last_name", "user__username", "user__email"]
    list_display = ["get_name", "get_email", "gender", "sponsored"]
    list_filter = ["gender", "sponsored"]

    @admin.display(description="Name", ordering="user__first_name")
    def get_name(self, obj: Player) -> str:
        return obj.user.first_name + " " + obj.user.last_name

    @admin.display(description="Email", ordering="user__username")
    def get_email(self, obj: Player) -> str:
        return obj.user.username

    def get_search_results(
        self,
        request: HttpRequest,
        queryset: QuerySet[Player],
        search_term: str,
    ) -> tuple[QuerySet[Player], bool]:
        # Add annotation for full name search
        queryset = queryset.annotate(
            full_name=Concat(
                "user__first_name", Value(" "), "user__last_name", output_field=CharField()
            )
        )
        # Add full name to search
        if search_term:
            queryset = queryset.filter(
                Q(full_name__icontains=search_term) | Q(user__email__icontains=search_term)
            )
        return (
            queryset.annotate(
                display_label=Concat(
                    "user__first_name",
                    Value(" "),
                    "user__last_name",
                    Value(" ("),
                    "user__email",
                    Value(")"),
                    output_field=CharField(),
                )
            ),
            False,
        )

    def get_admin_display_value(self, obj: Player) -> str:
        return f"{obj.user.get_full_name()} ({obj.user.email})"


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
    search_fields = ["name", "slug"]
    list_display = ["name", "slug"]

    def get_search_results(
        self,
        request: HttpRequest,
        queryset: QuerySet[Team],
        search_term: str,
    ) -> tuple[QuerySet[Team], bool]:
        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term) | Q(slug__icontains=search_term)
            )
        return (
            queryset.annotate(
                display_label=Concat(
                    "name", Value(" ("), "slug", Value(")"), output_field=CharField()
                )
            ),
            False,
        )

    def get_admin_display_value(self, obj: Team) -> str:
        return str(obj)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin[Event]):
    search_fields = ["title"]
    list_display = ["title", "tier"]


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin[Tournament]):
    search_fields = ["event__title"]
    list_display = ["get_name"]
    filter_horizontal = ("volunteers", "teams", "partial_teams")

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


@admin.register(Bracket)
class BracketAdmin(admin.ModelAdmin[Bracket]):
    search_fields = ["tournament__event__title"]
    list_display = ["get_name", "name"]

    @admin.display(description="Tournament Name", ordering="tournament__event__title")
    def get_name(self, obj: Pool) -> str:
        return obj.tournament.event.title


@admin.register(CrossPool)
class CrossPoolAdmin(admin.ModelAdmin[CrossPool]):
    search_fields = ["tournament__event__title"]
    list_display = ["get_name"]

    @admin.display(description="Tournament Name", ordering="tournament__event__title")
    def get_name(self, obj: Pool) -> str:
        return obj.tournament.event.title


@admin.register(PositionPool)
class PositionPoolAdmin(admin.ModelAdmin[PositionPool]):
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


@admin.register(MatchStats)
class MatchStatsAdmin(admin.ModelAdmin[MatchStats]):
    search_fields = ["tournament__event__title"]
    list_display = ["get_tournament_name", "get_match_name"]

    @admin.display(description="Tournament Name", ordering="tournament__event__title")
    def get_tournament_name(self, obj: MatchStats) -> str:
        return obj.tournament.event.title

    @admin.display(description="Match Name", ordering="match__name")
    def get_match_name(self, obj: MatchStats) -> str:
        match_name = obj.match.name or ""
        return match_name


@admin.register(MatchEvent)
class MatchEventAdmin(admin.ModelAdmin[MatchEvent]):
    search_fields = ["team__name"]
    list_display = ["get_tournament_name", "get_match_name"]

    @admin.display(description="Tournament Name", ordering="stats__match__tournament__event__title")
    def get_tournament_name(self, obj: MatchEvent) -> str:
        return obj.stats.match.tournament.event.title

    @admin.display(description="Match Name", ordering="stats__match__name")
    def get_match_name(self, obj: MatchEvent) -> str:
        match_name = obj.stats.match.name or ""
        return match_name


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
        "get_sponsored",
    ]
    list_filter = ["is_active", "player__sponsored"]
    actions = [export_as_csv]

    @admin.display(description="Player Name", ordering="player__user__first_name")
    def get_name(self, obj: Membership) -> str:
        return obj.player.user.first_name

    @admin.display(description="Sponsored", ordering="player__sponsored")
    def get_sponsored(self, obj: Membership) -> bool:
        return obj.player.sponsored


@admin.register(RazorpayTransaction)
class RazorpayTransactionAdmin(admin.ModelAdmin[RazorpayTransaction]):
    change_list_template = "admin/razorpay_transaction.html"
    search_fields = ["user__first_name"]
    list_display = [
        "get_name",
        "type",
        "order_id",
        "payment_id",
        "amount",
        "payment_date",
        "status",
    ]
    list_filter = ["status", "type", "payment_date"]
    date_hierarchy = "payment_date"
    actions = [export_as_csv]

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> TemplateResponse:
        response = super().changelist_view(request, extra_context or {})

        if isinstance(response, TemplateResponse):
            try:
                context_data = response.context_data
                if context_data is not None:
                    qs = context_data["cl"].queryset
                    # Calculate total amount for filtered queryset
                    metrics = qs.aggregate(
                        total_completed=Sum("amount", filter=Q(status="completed"), default=0),
                    )

                    context_data.update(
                        {
                            "total_completed_amount": metrics["total_completed"] / 100,
                        }
                    )
            except (AttributeError, KeyError):
                pass

            return response

        # If response is not TemplateResponse, create one
        return TemplateResponse(request, self.change_list_template, {})

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


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin[Series]):
    search_fields = ["name"]
    list_display = ["name"]

    filter_horizontal = ("teams",)


@admin.register(SeriesRosterInvitation)
class SeriesRosterInvitationAdmin(admin.ModelAdmin[SeriesRosterInvitation]):
    search_fields = [
        "from_user__username",
        "to_player__user__first_name",
        "to_player__user__last_name",
    ]
    list_display = ["get_name", "get_email", "get_team"]

    @admin.display(description="From", ordering="from_user__username")
    def get_name(self, obj: SeriesRosterInvitation) -> str:
        return obj.from_user.username

    @admin.display(description="To", ordering="to_player__user__first_name")
    def get_email(self, obj: SeriesRosterInvitation) -> str:
        return obj.to_player.user.get_full_name()

    @admin.display(description="Team", ordering="team__name")
    def get_team(self, obj: SeriesRosterInvitation) -> str:
        return obj.team.name


@admin.register(SeriesRegistration)
class SeriesRegistrationAdmin(admin.ModelAdmin[SeriesRegistration]):
    search_fields = [
        "team__name",
        "player__user__first_name",
        "player__user__last_name",
        "player__user__email",
    ]
    list_display = ["get_name", "get_email", "get_team"]
    autocomplete_fields = ["player", "team"]

    @admin.display(description="Series", ordering="series__name")
    def get_name(self, obj: SeriesRegistration) -> str:
        return obj.series.name

    @admin.display(description="Team", ordering="team__name")
    def get_email(self, obj: SeriesRegistration) -> str:
        return obj.team.name

    @admin.display(description="Player", ordering="player__user__first_name")
    def get_team(self, obj: SeriesRegistration) -> str:
        return obj.player.user.get_full_name()


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin[Registration]):
    search_fields = [
        "team__name",
        "player__user__first_name",
        "player__user__last_name",
        "player__user__username",
    ]
    list_display = ["get_name", "get_email", "get_team"]
    autocomplete_fields = ["player", "team"]

    @admin.display(description="Player", ordering="player__user__first_name")
    def get_name(self, obj: Registration) -> str:
        return obj.player.user.get_full_name()

    @admin.display(description="Event", ordering="event__title")
    def get_email(self, obj: Registration) -> str:
        return obj.event.title

    @admin.display(description="Team", ordering="team__name")
    def get_team(self, obj: Registration) -> str:
        return obj.team.name


@admin.register(Guardianship)
class GuardianshipAdmin(admin.ModelAdmin[Guardianship]):
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__username",
        "player__user__first_name",
        "player__user__last_name",
        "player__user__username",
    ]
    list_display = ["get_name", "get_email"]

    @admin.display(description="User", ordering="user__first_name")
    def get_name(self, obj: Guardianship) -> str:
        return obj.user.get_full_name()

    @admin.display(description="Player", ordering="player__user__first_name")
    def get_email(self, obj: Guardianship) -> str:
        return obj.player.user.get_full_name()


@admin.register(Accreditation)
class AccreditationAdmin(admin.ModelAdmin[Accreditation]):
    search_fields = [
        "player__user__first_name",
        "player__user__last_name",
        "player__user__username",
    ]
    list_display = ["get_email", "is_valid", "level"]
    list_filter = ["is_valid", "level"]

    @admin.display(description="Player", ordering="player__user__first_name")
    def get_email(self, obj: Guardianship) -> str:
        return obj.player.user.get_full_name()

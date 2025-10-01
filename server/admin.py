import csv
from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import CharField, Q, QuerySet, Sum, Value
from django.db.models.functions import Concat
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.utils.html import format_html

from server.announcements.models import Announcement
from server.core.models import (
    Accreditation,
    Guardianship,
    Player,
    Team,
    User,
)
from server.election.models import (
    Candidate,
    Election,
    ElectionResult,
    EligibleVoter,
    RankedVote,
    RankedVoteChoice,
    VoterVerification,
)
from server.membership.models import Membership
from server.season.models import Season
from server.series.models import Series, SeriesRegistration, SeriesRosterInvitation
from server.servicerequests.models import ServiceRequest
from server.task.manager import TaskManager
from server.task.models import Task
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
    SpiritScore,
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


@admin.action(description="Set sponsored to False")
def set_sponsored_false(
    self: admin.ModelAdmin[Player],
    request: HttpRequest,
    queryset: QuerySet[Player],
) -> None:
    """Set sponsored status to False for all selected players"""
    updated_count = queryset.update(sponsored=False)
    self.message_user(
        request,
        f"Successfully updated {updated_count} player(s) to set sponsored=False.",
    )


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin[Player]):
    search_fields = ["user__first_name", "user__last_name", "user__username", "user__email"]
    list_display = ["get_name", "get_email", "gender", "sponsored"]
    list_filter = ["gender", "sponsored"]
    actions = [export_as_csv, set_sponsored_false]

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


class TournamentFilter(admin.SimpleListFilter):
    title = "Tournament"
    parameter_name = "tournament"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[MatchEvent]
    ) -> list[tuple[int, str]]:
        tournaments = Tournament.objects.all().order_by("event__title")
        return [(t.id, t.event.title) for t in tournaments]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[MatchEvent]
    ) -> QuerySet[MatchEvent]:
        if self.value():
            return queryset.filter(stats__match__tournament_id=self.value())
        return queryset


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
    search_fields = ["team__name", "stats__match__name", "stats__match__tournament__event__title"]
    list_display = [
        "get_tournament_name",
        "get_match_name",
        "get_team_name",
        "get_event_type",
        "get_event_details",
        "time",
    ]
    list_filter = ["type", "team", TournamentFilter]
    raw_id_fields = (
        "players",
        "scored_by",
        "assisted_by",
        "drop_by",
        "throwaway_by",
        "block_by",
    )

    @admin.display(description="Tournament Name", ordering="stats__match__tournament__event__title")
    def get_tournament_name(self, obj: MatchEvent) -> str:
        return obj.stats.match.tournament.event.title

    @admin.display(description="Match Name", ordering="stats__match__name")
    def get_match_name(self, obj: MatchEvent) -> str:
        match_name = obj.stats.match.name or ""
        return match_name

    @admin.display(description="Team", ordering="team__name")
    def get_team_name(self, obj: MatchEvent) -> str:
        return obj.team.name

    @admin.display(description="Event Type", ordering="type")
    def get_event_type(self, obj: MatchEvent) -> str:
        return obj.get_type_display()

    @admin.display(description="Event Details")
    def get_event_details(self, obj: MatchEvent) -> str:
        details = []
        if obj.type == MatchEvent.EventType.SCORE:
            if obj.scored_by:
                details.append(f"Scored by: {obj.scored_by.user.get_full_name()}")
            if obj.assisted_by:
                details.append(f"Assisted by: {obj.assisted_by.user.get_full_name()}")
        elif obj.type == MatchEvent.EventType.DROP:
            if obj.drop_by:
                details.append(f"Dropped by: {obj.drop_by.user.get_full_name()}")
        elif obj.type == MatchEvent.EventType.THROWAWAY:
            if obj.throwaway_by:
                details.append(f"Throwaway by: {obj.throwaway_by.user.get_full_name()}")
        elif obj.type == MatchEvent.EventType.BLOCK:
            if obj.block_by:
                details.append(f"Blocked by: {obj.block_by.user.get_full_name()}")
        elif obj.type == MatchEvent.EventType.LINE_SELECTED:
            players = [player.user.get_full_name() for player in obj.players.all()]
            if players:
                details.append(f"Line: {', '.join(players)}")
        return " | ".join(details) if details else ""


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


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin[Election]):
    search_fields = ["title", "description"]
    list_display = ["title", "voting_method", "num_winners", "is_active", "start_date", "end_date"]
    list_filter = ["voting_method", "is_active", "start_date", "end_date"]
    date_hierarchy = "start_date"


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin[Candidate]):
    search_fields = ["user__first_name", "user__last_name", "user__email", "election__title"]
    list_display = ["get_name", "get_election", "created_at"]
    list_filter = ["election", "created_at"]

    @admin.display(description="Name", ordering="user__first_name")
    def get_name(self, obj: Candidate) -> str:
        return obj.user.get_full_name()

    @admin.display(description="Election", ordering="election__title")
    def get_election(self, obj: Candidate) -> str:
        return obj.election.title


@admin.register(RankedVote)
class RankedVoteAdmin(admin.ModelAdmin[RankedVote]):
    search_fields = ["election__title", "voter_hash"]
    list_display = ["get_election", "voter_hash", "timestamp"]
    list_filter = ["election", "timestamp"]
    date_hierarchy = "timestamp"

    @admin.display(description="Election", ordering="election__title")
    def get_election(self, obj: RankedVote) -> str:
        return obj.election.title


@admin.register(RankedVoteChoice)
class RankedVoteChoiceAdmin(admin.ModelAdmin[RankedVoteChoice]):
    search_fields = [
        "vote__election__title",
        "candidate__user__first_name",
        "candidate__user__last_name",
    ]
    list_display = ["get_election", "get_candidate", "rank"]
    list_filter = ["vote__election", "rank"]

    @admin.display(description="Election", ordering="vote__election__title")
    def get_election(self, obj: RankedVoteChoice) -> str:
        return obj.vote.election.title

    @admin.display(description="Candidate", ordering="candidate__user__first_name")
    def get_candidate(self, obj: RankedVoteChoice) -> str:
        return obj.candidate.user.get_full_name()


@admin.register(VoterVerification)
class VoterVerificationAdmin(admin.ModelAdmin[VoterVerification]):
    search_fields = ["election__title", "user__email", "verification_token"]
    list_display = ["get_election", "get_user", "is_used", "created_at"]
    list_filter = ["election", "is_used", "created_at"]
    date_hierarchy = "created_at"

    @admin.display(description="Election", ordering="election__title")
    def get_election(self, obj: VoterVerification) -> str:
        return obj.election.title

    @admin.display(description="User", ordering="user__email")
    def get_user(self, obj: VoterVerification) -> str:
        return obj.user.email


@admin.register(EligibleVoter)
class EligibleVoterAdmin(admin.ModelAdmin[EligibleVoter]):
    search_fields = ["election__title", "user__email"]
    list_display = ["get_election", "get_user", "created_at"]
    list_filter = ["election", "created_at"]
    date_hierarchy = "created_at"

    @admin.display(description="Election", ordering="election__title")
    def get_election(self, obj: EligibleVoter) -> str:
        return obj.election.title

    @admin.display(description="User", ordering="user__email")
    def get_user(self, obj: EligibleVoter) -> str:
        return obj.user.email


@admin.register(ElectionResult)
class ElectionResultAdmin(admin.ModelAdmin[ElectionResult]):
    search_fields = ["election__title", "candidate__user__first_name", "candidate__user__last_name"]
    list_display = [
        "get_election",
        "get_candidate",
        "round_number",
        "votes",
        "status",
        "created_at",
    ]
    list_filter = ["election", "round_number", "status", "created_at"]
    date_hierarchy = "created_at"

    @admin.display(description="Election", ordering="election__title")
    def get_election(self, obj: ElectionResult) -> str:
        return obj.election.title

    @admin.display(description="Candidate", ordering="candidate__user__first_name")
    def get_candidate(self, obj: ElectionResult) -> str:
        return obj.candidate.user.get_full_name()


@admin.register(SpiritScore)
class SpiritScoreAdmin(admin.ModelAdmin[SpiritScore]):
    pass


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin[ServiceRequest]):
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    list_display = ["get_user", "type", "status", "created_at"]
    list_filter = ["type", "status", "created_at"]
    date_hierarchy = "created_at"
    filter_horizontal = ("service_players",)

    @admin.display(description="User", ordering="user__first_name")
    def get_user(self, obj: ServiceRequest) -> str:
        return obj.user.get_full_name()


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin[Announcement]):
    list_display = ["title", "type", "slug", "author", "created_at", "has_action"]
    list_filter = ["type", "created_at", "author"]
    search_fields = ["title", "slug", "content", "author__first_name", "author__last_name"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    readonly_fields = ["slug"]

    fieldsets = (
        (None, {"fields": ("title", "slug", "type", "content", "is_members_only", "is_published")}),
        (
            "Call to Action (Optional)",
            {
                "fields": ("action_text", "action_url"),
            },
        ),
    )

    def save_model(self, request: HttpRequest, obj: Announcement, form: Any, change: bool) -> None:
        if not change:  # Only for new objects
            obj.author = request.user  # type: ignore[assignment]
        super().save_model(request, obj, form, change)

    @admin.display(description="Call to Action")
    def has_action(self, obj: Announcement) -> str:
        """Display whether announcement has CTA"""
        if obj.action_text and obj.action_url:
            return format_html('<span style="color: green;">✓ {}</span>', obj.action_text)
        return format_html('<span style="color: gray;">No CTA</span>')

    def get_queryset(self, request: HttpRequest) -> QuerySet[Announcement]:
        return super().get_queryset(request).select_related("author")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin[Task]):
    list_display = [
        "id",
        "type",
        "get_status",
        "created_at",
        "started_at",
        "completed_at",
    ]
    list_filter = ["type", "created_at", "started_at", "completed_at", "failed_at"]
    search_fields = ["id", "type"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "type",
        "data",
        "created_at",
        "started_at",
        "completed_at",
        "failed_at",
        "result",
        "error",
    ]
    change_list_template = "admin/task_changelist.html"

    @admin.display(description="Status")
    def get_status(self, obj: Task) -> str:
        """Display the current status of the task"""
        if obj.failed_at:
            return format_html('<span style="color: red;">Failed</span>')
        elif obj.completed_at:
            return format_html('<span style="color: green;">Completed</span>')
        elif obj.started_at:
            return format_html('<span style="color: orange;">Running</span>')
        else:
            return format_html('<span style="color: blue;">Pending</span>')

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Prevent adding tasks through admin - they should be added programmatically
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Task | None = None) -> bool:
        # Allow deletion of completed or failed tasks
        return obj is None or obj.completed_at is not None or obj.failed_at is not None

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> TemplateResponse | HttpResponse:
        extra_context = extra_context or {}

        # Add task statistics to context
        extra_context["task_stats"] = TaskManager.get_task_stats()

        if request.method == "POST" and "send_test_email" in request.POST:
            test_email = request.POST.get("test_email", "").strip()
            if test_email:
                from django.core.mail import EmailMultiAlternatives

                from server.task.helpers import queue_emails

                email = EmailMultiAlternatives(
                    subject="Test Email from Hub Task Queue",
                    body="This is a test email sent via the task queue system.",
                    from_email=None,
                    to=[test_email],
                )
                email.attach_alternative(
                    "<h1>Test Email</h1><p>This is a test email sent via the task queue system.</p>",
                    "text/html",
                )

                try:
                    tasks = queue_emails([email])
                    self.message_user(
                        request,
                        f"Test email task created (Task ID: {tasks[0].id}) for {test_email}",
                        level="success",
                    )
                except Exception as e:
                    self.message_user(request, f"Failed to queue test email: {e}", level="error")

        return super().changelist_view(request, extra_context)

import csv
from typing import Any

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import CharField, Q, QuerySet, Sum, Value
from django.db.models.functions import Concat
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html

from server.admin_views import REFUND_PERM
from server.announcements.models import Announcement
from server.core.models import Accreditation, Guardianship, Player, Team, User
from server.duplicates import review
from server.duplicates.flow import FlowError, approve_staff, reject_staff
from server.duplicates.merge import (
    MergeBlockedError,
    MergeFieldError,
    MergeIncompleteError,
    RelationMove,
    build_plan,
    check_blockers,
)
from server.duplicates.models import (
    AccountMerge,
    AliasHeldError,
    ClusterEvent,
    ClusterMember,
    DuplicateCluster,
    EmailAlias,
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
from server.forms.models import Form, FormResponse
from server.payment_account.models import PaymentAccount, SecretsUnavailable, encrypt
from server.receipts.models import Receipt
from server.receipts.money import format_inr
from server.registration.models import RosterSwap
from server.season.models import Season
from server.series.models import Series, SeriesRegistration, SeriesRosterInvitation
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType
from server.subscription import catalog, sponsorship
from server.subscription.models import (
    SponsorshipGrant,
    Subscription,
    SubscriptionPlan,
    SubscriptionType,
    SubscriptionTypeScope,
)
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
    SwissRound,
    Tournament,
    TournamentField,
)
from server.transaction.client.razorpay import client_for
from server.transaction.models import (
    ManualTransaction,
    PhonePeTransaction,
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)


@admin.action(description="Export Selected")
def export_as_csv(
    self: admin.ModelAdmin[
        Subscription | RazorpayTransaction | PhonePeTransaction | ManualTransaction
    ],
    request: HttpRequest,
    queryset: QuerySet[Subscription | RazorpayTransaction | PhonePeTransaction | ManualTransaction],
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


class SponsorshipGrantInline(admin.TabularInline[SponsorshipGrant, Player]):
    model = SponsorshipGrant
    extra = 0
    fields = ["season", "granted_at", "granted_by", "request", "note"]
    readonly_fields = ["granted_at"]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin[Player]):
    search_fields = ["user__first_name", "user__last_name", "user__username", "user__email"]
    list_display = ["get_name", "get_email", "gender"]
    list_filter = ["gender"]
    actions = [export_as_csv]
    inlines = [SponsorshipGrantInline]
    # Player.sponsored is dead after per-season sponsorship, and nothing
    # reads it any more, so it is kept off this form too: ticking it would
    # look like granting sponsorship and grant nothing. A grant is per
    # season, made in the inline below, and revoked by deleting it there.
    exclude = ["sponsored"]
    # The number is assigned once and kept for life, and it is printed on
    # waivers and certificates, so a typo here could not be taken back and
    # a repeat would break the unique column. Readable, not editable.
    readonly_fields = ["iu_id"]

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


class PaymentAccountForm(forms.ModelForm):  # type: ignore[type-arg]
    # Write-only: the stored secrets are never put back into the page.
    new_key_secret = forms.CharField(
        label="Key secret",
        required=False,
        widget=forms.PasswordInput,
        help_text="Leave blank to keep the current secret.",
    )
    new_webhook_secret = forms.CharField(
        label="Webhook secret",
        required=False,
        widget=forms.PasswordInput,
        help_text="The secret typed into the webhook in the state's Razorpay dashboard. "
        "Leave blank to keep the current one.",
    )

    class Meta:
        model = PaymentAccount
        fields = ["name", "slug", "key_id", "viewers", "is_active"]
        help_texts = {
            "key_id": "Rotating keys? Enter the new key ID and its secret together. "
            "To move a state to a different Razorpay account, add a new payment account instead."
        }

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if not self.instance.key_secret_encrypted and not data.get("new_key_secret"):
            self.add_error("new_key_secret", "Required for a new account.")
        elif "key_id" in self.changed_data and not data.get("new_key_secret"):
            # The old secret belongs to the old key: every order would fail.
            self.add_error("new_key_secret", "A new key ID needs its new key secret too.")
        if data.get("new_key_secret") or data.get("new_webhook_secret"):
            try:
                encrypt("check")
            except SecretsUnavailable:
                # Refuse here: an unhandled error in save() would put the typed
                # secret in front of Sentry.
                raise forms.ValidationError(
                    "This server can't encrypt secrets: "
                    "PAYMENT_ACCOUNT_ENCRYPTION_KEY is missing or invalid."
                ) from None
        return data

    def save(self, commit: bool = True) -> PaymentAccount:
        account = super().save(commit=False)
        if self.cleaned_data.get("new_key_secret"):
            account.key_secret = self.cleaned_data["new_key_secret"]
        if self.cleaned_data.get("new_webhook_secret"):
            account.webhook_secret = self.cleaned_data["new_webhook_secret"]
        if commit:
            account.save()
            self.save_m2m()
        return account


@admin.register(PaymentAccount)
class PaymentAccountAdmin(admin.ModelAdmin[PaymentAccount]):
    form = PaymentAccountForm
    list_display = ["name", "slug", "mode", "is_active"]
    search_fields = ["name", "slug"]
    autocomplete_fields = ["viewers"]
    readonly_fields = ["mode", "secrets", "webhook_path"]
    actions = ["test_connection"]

    @admin.display(description="Mode")
    def mode(self, obj: PaymentAccount) -> str:
        mode = "TEST MODE" if obj.is_test_mode else "LIVE"
        if obj.keys_match_environment:
            return mode
        ours = "live" if obj.is_test_mode else "test"
        return f"{mode} — does not match this server's {ours} keys"

    @admin.display(description="Secrets")
    def secrets(self, obj: PaymentAccount) -> str:
        key = "set" if obj.key_secret_encrypted else "missing"
        hook = "set" if obj.webhook_secret_encrypted else "missing"
        return f"Key secret {key} · webhook secret {hook}"

    @admin.display(description="Webhook")
    def webhook_path(self, obj: PaymentAccount) -> str:
        if not obj.slug:
            return "Save first."
        return format_html(
            "In the state's Razorpay dashboard, add a webhook for this site's address "
            "followed by <code>/api/transactions/razorpay/webhook/{}</code>, subscribed "
            "to <code>payment.captured</code> and <code>order.paid</code>, with the "
            "webhook secret entered here.",
            obj.slug,
        )

    @admin.action(description="Test connection to Razorpay")
    def test_connection(self, request: HttpRequest, queryset: QuerySet[PaymentAccount]) -> None:
        for account in queryset:
            try:
                client_for(account).order.all({"count": 1})
            except Exception as error:  # Razorpay's own message is what staff need
                self.message_user(request, f"{account.name}: {error}", messages.ERROR)
            else:
                mode = "test mode" if account.is_test_mode else "live"
                self.message_user(request, f"{account.name}: connected ({mode}).", messages.SUCCESS)


class EventAdminForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = Event
        fields = "__all__"  # noqa: DJ007

    def clean_payment_account(self) -> PaymentAccount | None:
        chosen = self.cleaned_data.get("payment_account")
        # Read the stored value from the database, not self.instance: an earlier
        # validation of a form bound to this same instance (as in the tests) has
        # already written its choice onto it. Within one validation, _post_clean
        # only writes onto the instance after clean_<field> has run.
        stored = Event.objects.filter(pk=self.instance.pk).values_list("payment_account", flat=True)
        changed = self.instance.pk and stored.first() != (chosen.pk if chosen else None)
        if (
            changed
            and RazorpayTransaction.objects.filter(
                event=self.instance, status__in=RazorpayTransaction.SETTLED
            ).exists()
        ):
            raise forms.ValidationError(
                "Payments have already been taken for this event, "
                "so where its fees go can't change."
            )
        return chosen


@admin.register(Event)
class EventAdmin(admin.ModelAdmin[Event]):
    form = EventAdminForm
    search_fields = ["title"]
    list_display = ["title", "tier"]


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin[Tournament]):
    search_fields = ["event__title"]
    list_display = ["get_name"]
    filter_horizontal = ("volunteers", "directors", "teams", "partial_teams")

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


@admin.register(SwissRound)
class SwissRoundAdmin(admin.ModelAdmin[SwissRound]):
    search_fields = ["tournament__event__title"]
    list_display = ["get_name", "name", "current_round", "num_rounds"]

    @admin.display(description="Tournament Name", ordering="tournament__event__title")
    def get_name(self, obj: SwissRound) -> str:
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


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin[Subscription]):
    search_fields = ["player__user__first_name"]
    list_display = [
        "get_name",
        "season",
        "get_tier",
        "amount_paid",
        "is_active",
        "refunded_at",
    ]
    list_filter = [
        "season",
        "plan__type",
        "is_active",
        ("refunded_at", admin.EmptyFieldListFilter),
    ]
    list_select_related = ["player__user", "season", "plan__type"]
    actions = [export_as_csv, "refund_completely"]
    # subscription_number and is_annual are retained on the model only for
    # the deploy window (a still-running previous release reads the
    # columns); nothing should read or write them through this form.
    exclude = ["subscription_number", "is_annual"]

    @admin.display(description="Player Name", ordering="player__user__first_name")
    def get_name(self, obj: Subscription) -> str:
        return obj.player.user.first_name

    @admin.display(description="Tier", ordering="plan__type__display_order")
    def get_tier(self, obj: Subscription) -> str:
        return obj.plan.type.name if obj.plan is not None else "—"

    def has_refund_permission(self, request: HttpRequest) -> bool:
        return request.user.has_perm(REFUND_PERM)

    @admin.action(description="Refund this subscription completely", permissions=["refund"])
    def refund_completely(
        self, request: HttpRequest, queryset: QuerySet[Subscription]
    ) -> HttpResponse | None:
        items = list(queryset)
        if len(items) != 1:
            self.message_user(request, "Refund one subscription at a time", messages.WARNING)
            return None
        # Straight to the confirmation page: no money moves until staff confirm.
        return redirect("admin:refund_subscription", items[0].pk)


class NeedsReviewFilter(admin.SimpleListFilter):
    """Orders with a line staff have to look at — Task 9's flagged payments."""

    title = "needs review"
    parameter_name = "needs_review"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        return [("yes", "Yes"), ("no", "No")]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[RazorpayTransaction]
    ) -> QuerySet[RazorpayTransaction]:
        flagged = RazorpayTransactionPlayer.objects.filter(needs_review=True).values("transaction")
        if self.value() == "yes":
            return queryset.filter(pk__in=flagged)
        if self.value() == "no":
            return queryset.exclude(pk__in=flagged)
        return queryset


class RazorpayTransactionPlayerInline(
    admin.TabularInline[RazorpayTransactionPlayer, RazorpayTransaction]
):
    model = RazorpayTransactionPlayer
    extra = 0
    readonly_fields = ["refund_link"]

    def get_fields(self, request: HttpRequest, obj: Any = None) -> list[str]:
        fields = ["player", "plan", "amount", "subscription", "needs_review", "review_note"]
        # The button is only shown to staff who may actually refund; the view
        # refuses anyone else anyway.
        if request.user.has_perm(REFUND_PERM):
            fields.append("refund_link")
        return fields

    @admin.display(description="Refund")
    def refund_link(self, obj: RazorpayTransactionPlayer) -> str:
        if not obj.pk or not obj.amount:
            return "—"
        return format_html(
            '<a class="button" href="{}">Refund ₹{}</a>',
            reverse("admin:refund_line", args=[obj.pk]),
            obj.amount // 100,
        )


class RazorpayRefundInline(admin.TabularInline[RazorpayRefund, RazorpayTransaction]):
    model = RazorpayRefund
    extra = 0
    fields = ("amount", "status", "source", "reason", "created_by", "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(RazorpayTransaction)
class RazorpayTransactionAdmin(admin.ModelAdmin[RazorpayTransaction]):
    change_list_template = "admin/razorpay_transaction.html"
    search_fields = ["user__first_name"]
    inlines = [RazorpayTransactionPlayerInline, RazorpayRefundInline]
    list_display = [
        "get_name",
        "type",
        "order_id",
        "payment_id",
        "amount",
        "payment_date",
        "status",
        "account",
    ]
    list_filter = ["status", "type", NeedsReviewFilter, "payment_date", "account"]
    date_hierarchy = "payment_date"
    actions = [export_as_csv]

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> list[str]:
        # The account is fixed when the order is placed, never changed after.
        fixed = ["account", "notes"]
        if obj is not None and request.user.has_perm(REFUND_PERM):
            return [*fixed, "refund_order_link"]
        return fixed

    @admin.display(description="Refund the whole order")
    def refund_order_link(self, obj: RazorpayTransaction) -> str:
        return format_html(
            '<a class="button" href="{}">Refund what is left of this order</a>',
            reverse("admin:refund_order", args=[obj.pk]),
        )

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


class SubscriptionTypeScopeInline(admin.TabularInline[SubscriptionTypeScope, SubscriptionType]):
    model = SubscriptionTypeScope
    extra = 0


@admin.register(SubscriptionType)
class SubscriptionTypeAdmin(admin.ModelAdmin[SubscriptionType]):
    list_display = ["name", "slug", "requires_grant", "display_order"]
    inlines = [SubscriptionTypeScopeInline]


class SubscriptionPlanInline(admin.TabularInline[SubscriptionPlan, Season]):
    model = SubscriptionPlan
    extra = 0


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin[SubscriptionPlan]):
    list_display = ["season", "type", "amount", "is_available"]
    list_filter = ["season", "type", "is_available"]


@admin.register(SponsorshipGrant)
class SponsorshipGrantAdmin(admin.ModelAdmin[SponsorshipGrant]):
    list_display = ["player", "season", "granted_at", "granted_by"]
    list_filter = ["season"]
    search_fields = ["player__user__email", "player__user__first_name"]
    list_select_related = ["player__user", "season", "granted_by"]


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
    list_display = ["name", "start_date", "end_date"]
    inlines = [SubscriptionPlanInline]

    def save_model(self, request: HttpRequest, obj: Season, form: Any, change: bool) -> None:
        super().save_model(request, obj, form, change)
        if change:
            return
        previous = (
            Season.objects.exclude(pk=obj.pk)
            .filter(start_date__lt=obj.start_date)
            .order_by("-start_date")
            .first()
        )
        if previous is None:
            return
        copied = catalog.copy_plans(previous, obj)
        if copied:
            self.message_user(request, f"Copied {copied} plan(s) from {previous.name}. Check them.")


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


class RosterRowAdmin:
    """Who a roster row is for, once it exists, is not an edit.

    A player's teams follow their roster rows, and the receivers that keep them
    in step (server/tournament/models.py) read the row as it was created. Moving
    a row to another player or team behind their back would leave the old team
    on one profile and the new team off the other. Deleting the row and adding
    the right one does the same job and keeps both profiles honest.
    """

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> tuple[str, ...]:
        return ("player", "team") if obj is not None else ()


@admin.register(SeriesRegistration)
class SeriesRegistrationAdmin(RosterRowAdmin, admin.ModelAdmin[SeriesRegistration]):
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
class RegistrationAdmin(RosterRowAdmin, admin.ModelAdmin[Registration]):
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


def _describe(move: RelationMove) -> str:
    line = f"{move.label.split('.', 1)[1]}: {move.moved} moved"
    if move.collided:
        theirs = move.collided - move.primary_loses
        line += (
            f"; {move.collided} clashed, deleting {theirs} of the other account's rows"
            f" and {move.primary_loses} of the kept account's"
        )
    return line


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin[ServiceRequest]):
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    list_display = ["get_user", "type", "status", "season", "created_at"]
    list_filter = ["type", "status", "season", "created_at"]
    date_hierarchy = "created_at"
    filter_horizontal = ("service_players",)
    actions = ["approve_sponsorship", "approve_and_merge", "reject_merge"]

    @admin.action(description="Sponsorship requests: approve", permissions=["change"])
    def approve_sponsorship(self, request: HttpRequest, queryset: QuerySet[ServiceRequest]) -> None:
        """Approve, and grant the season explicitly.

        The status signal grants too, but it cannot help a request that was
        created already approved: the M2M players are not attached yet when
        post_save fires. Granting here is what actually entitles them.
        """
        for item in queryset.filter(type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION):
            season = item.season or Season.current()
            if season is None:
                self.message_user(request, f"Request {item.pk}: no season to grant", messages.ERROR)
                continue
            # Granted before the status is saved, so this records who approved
            # it: the status signal grants too, and whichever runs first wins.
            players = list(item.service_players.all())
            for player in players:
                sponsorship.grant(
                    player,
                    season,
                    by=request.user,  # type: ignore[arg-type]
                    request=item,
                )
            if item.status != ServiceRequestStatus.APPROVED:
                item.status = ServiceRequestStatus.APPROVED
                item.save()
            self.message_user(
                request, f"Request {item.pk}: {len(players)} player(s) sponsored for {season.name}"
            )

    @admin.display(description="User", ordering="user__first_name")
    def get_user(self, obj: ServiceRequest) -> str:
        return obj.user.get_full_name()

    def has_merge_permission(self, request: HttpRequest) -> bool:
        return self.has_change_permission(request) and request.user.has_perm("server.delete_user")

    @admin.action(description="Merge requests: approve and merge", permissions=["merge"])
    def approve_and_merge(
        self, request: HttpRequest, queryset: QuerySet[ServiceRequest]
    ) -> TemplateResponse | None:
        items = list(queryset.filter(type=ServiceRequestType.REQUEST_ACCOUNT_MERGE))
        if len(items) != 1:
            self.message_user(request, "Approve merge requests one at a time", messages.WARNING)
            return None
        (item,) = items
        if request.POST.get("merge_confirmed") != "yes":
            return self._merge_review(request, item)
        try:
            approve_staff(item, request.user)  # type: ignore[arg-type]
        except (
            FlowError,
            MergeBlockedError,
            MergeFieldError,
            MergeIncompleteError,
            AliasHeldError,
        ) as error:
            if isinstance(error, MergeBlockedError):
                reason = ", ".join(error.args[0])
            elif isinstance(error, AliasHeldError):
                reason = f"{error.args[0]} already signs another account in"
            else:
                reason = str(error)
            self.message_user(request, f"Request {item.pk} not merged: {reason}", messages.ERROR)
        else:
            self.message_user(request, f"Request {item.pk} merged")
        return None

    def _merge_review(self, request: HttpRequest, item: ServiceRequest) -> TemplateResponse | None:
        row = ClusterMember.objects.filter(staff_request=item).select_related("user").first()
        if item.user_id == request.user.pk:
            error = "you asked for this merge, so someone else must approve it"
        elif item.status != ServiceRequestStatus.PENDING:
            error = "already closed"
        elif row is None or row.user is None:
            error = "the other account is gone"
        else:
            keeper, other = item.user, row.user
            return TemplateResponse(
                request,
                "admin/merge_review.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Approve this merge?",
                    "item": item,
                    "blockers": review.in_words(check_blockers(keeper, [other])),
                    "lines": review.compare(keeper, [other]),
                    "moves": [_describe(move) for move in build_plan(keeper, [other]).moves],
                },
            )
        self.message_user(request, f"Request {item.pk}: {error}", messages.ERROR)
        return None

    @admin.action(description="Merge requests: reject", permissions=["change"])
    def reject_merge(self, request: HttpRequest, queryset: QuerySet[ServiceRequest]) -> None:
        for item in queryset.filter(type=ServiceRequestType.REQUEST_ACCOUNT_MERGE):
            try:
                reject_staff(item, request.user)  # type: ignore[arg-type]
            except FlowError as error:
                self.message_user(request, f"Request {item.pk}: {error}", messages.ERROR)
            else:
                self.message_user(request, f"Request {item.pk} rejected")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin[Announcement]):
    list_display = ["title", "type", "slug", "author", "created_at", "has_action"]
    list_filter = ["type", "created_at", "author"]
    search_fields = ["title", "slug", "content", "author__first_name", "author__last_name"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    readonly_fields = ["slug"]
    change_form_template = "admin/announcement_change_form.html"

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "slug",
                    "type",
                    "content",
                    "is_members_only",
                    "is_published",
                )
            },
        ),
        (
            "Call to Action (Optional)",
            {
                "fields": ("action_text", "action_url"),
            },
        ),
    )

    def save_model(self, request: HttpRequest, obj: Announcement, form: Any, change: bool) -> None:
        if not change:
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

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        if request.method == "POST" and any(
            key in request.POST for key in ["send_to_all_users", "send_to_members", "send_to_email"]
        ):
            from django.http import HttpResponseRedirect

            from server.announcements.emails import (
                send_announcement_to_all_users,
                send_announcement_to_email,
                send_announcement_to_members,
            )

            announcement = Announcement.objects.get(pk=object_id)

            try:
                if "send_to_all_users" in request.POST:
                    tasks = send_announcement_to_all_users(announcement)
                    self.message_user(
                        request,
                        f"Queued {len(tasks)} announcement emails to all users",
                        level="success",
                    )
                elif "send_to_members" in request.POST:
                    tasks = send_announcement_to_members(announcement)
                    self.message_user(
                        request,
                        f"Queued {len(tasks)} announcement emails to active members",
                        level="success",
                    )
                elif "send_to_email" in request.POST:
                    test_email = request.POST.get("test_email", "").strip()
                    if test_email:
                        tasks = send_announcement_to_email(announcement, test_email)
                        self.message_user(
                            request, f"Queued test email to {test_email}", level="success"
                        )
            except Exception as e:
                self.message_user(request, f"Failed to queue emails: {e}", level="error")

            return HttpResponseRedirect(request.path)

        return super().change_view(request, object_id, form_url, extra_context)


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


class ReadOnly:
    """History: nothing here is added, edited or deleted by hand."""

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(AccountMerge)
class AccountMergeAdmin(ReadOnly, admin.ModelAdmin[AccountMerge]):
    list_display = ["id", "created_at", "primary_email", "cluster", "actor_email", "matched_by"]
    list_filter = ["created_at"]
    search_fields = ["primary_email", "duplicate_emails"]
    date_hierarchy = "created_at"


class ClusterMemberInline(ReadOnly, admin.TabularInline[ClusterMember, DuplicateCluster]):
    model = ClusterMember
    extra = 0
    fields = (
        "account_id",
        "account_email",
        "state",
        "proof",
        "verified_by_id",
        "merged_into_id",
        "merge",
        "staff_request",
    )
    readonly_fields = fields


class ClusterEventInline(ReadOnly, admin.TabularInline[ClusterEvent, DuplicateCluster]):
    model = ClusterEvent
    extra = 0
    ordering = ["-at"]
    fields = ("at", "kind", "member", "actor_email", "detail")
    readonly_fields = fields


@admin.register(DuplicateCluster)
class DuplicateClusterAdmin(ReadOnly, admin.ModelAdmin[DuplicateCluster]):
    list_display = ["id", "status", "origin", "matched_by", "created_at", "resolved_at"]
    list_filter = ["status", "origin"]
    inlines = [ClusterMemberInline, ClusterEventInline]


@admin.register(EmailAlias)
class EmailAliasAdmin(ReadOnly, admin.ModelAdmin[EmailAlias]):
    """Where an address a merge absorbed signs in now."""

    list_display = ["email", "user", "created_at"]
    search_fields = ["email", "user__email", "user__username"]
    list_select_related = ["user"]
    date_hierarchy = "created_at"


@admin.register(Form)
class FormAdmin(admin.ModelAdmin[Form]):
    list_display = ["title", "slug", "payment_amount", "is_active", "created_at"]
    search_fields = ["title", "slug"]
    list_filter = ["is_active"]


@admin.register(FormResponse)
class FormResponseAdmin(admin.ModelAdmin[FormResponse]):
    list_display = ["form", "user", "is_paid", "submitted_at"]
    search_fields = ["form__title", "user__first_name", "user__last_name", "user__email"]
    list_filter = ["form", "is_paid"]


@admin.register(RazorpayRefund)
class RazorpayRefundAdmin(ReadOnly, admin.ModelAdmin[RazorpayRefund]):
    """Every refund: who, when, why, how much, and how it went."""

    list_display = ["transaction", "line", "amount", "status", "source", "created_by", "created_at"]
    list_filter = ["status", "source", "created_at"]
    search_fields = ["transaction__order_id", "razorpay_refund_id"]
    list_select_related = ["transaction", "created_by"]
    date_hierarchy = "created_at"


@admin.register(Receipt)
class ReceiptAdmin(ReadOnly, admin.ModelAdmin[Receipt]):
    list_display = ["number", "kind", "issued_at", "payer_name", "total_inr", "open_link"]
    list_filter = ["kind", "financial_year"]
    search_fields = ["number", "payer_name", "payer_email", "order_id", "reference"]

    @admin.display(description="Total (INR)")
    def total_inr(self, receipt: Receipt) -> str:
        return format_inr(receipt.total)

    @admin.display(description="Document")
    def open_link(self, receipt: Receipt) -> str:
        return format_html('<a href="/receipts/{}" target="_blank">View</a>', receipt.pk)


@admin.register(RosterSwap)
class RosterSwapAdmin(ReadOnly, admin.ModelAdmin[RosterSwap]):
    """Every paid place a team passed from one player to another."""

    list_display = ("event", "team", "out_player", "in_player", "by", "at")
    readonly_fields = list_display
    list_select_related = ("event", "team", "out_player__user", "in_player__user", "by")
    date_hierarchy = "at"

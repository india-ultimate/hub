import time
from typing import Any

from django.conf import settings
from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.db.models import Model, Q, QuerySet

from server.core.models import Player, Team, User
from server.season.models import Season
from server.series.models import Role, is_playing_role
from server.subscription import catalog, eligibility
from server.subscription.pricing import UPGRADE, NeedsGrant, NotForSale, Quote, quote
from server.subscription.purchase import fulfil
from server.tournament.models import Event, Registration, Tournament
from server.tournament.utils import can_register_player_to_series_event, series_role
from server.types import message_response
from server.utils import calculate_late_penalty, is_today_in_between_dates, today

from .client import razorpay
from .models import (
    AuthenticatedHttpRequest,
    ManualTransaction,
    PaymentGateway,
    PhonePeTransaction,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)
from .schema import (
    PlayerRegistrationSchema,
    SubscriptionOrderSchema,
    TeamRegistrationSchema,
)


class ValidationError(Exception):
    """An order that cannot be placed, with the reason to show the buyer."""


def _names(players: list[Player]) -> str:
    names = ", ".join(sorted(player.user.get_full_name() for player in players))
    if len(names) > razorpay.RAZORPAY_NOTES_MAX:
        names = names[:500] + "..."
    return names


def build_subscription_order(
    order: SubscriptionOrderSchema,
) -> tuple[Season, list[tuple[Player, Quote]]]:
    """Check every line and price it, before any money is involved.

    Nothing about a subscription is created here. A payment that never
    completes must leave no trace, which is what the old code got wrong.
    """
    try:
        season = Season.objects.get(id=order.season_id)
    except Season.DoesNotExist as error:
        raise ValidationError("Season does not exist!") from error

    # Plans stay is_available after a season ends, and a tab opened before
    # the season picker was removed still offers them. Only the page stopped
    # asking; this is where the money is.
    if season.end_date < today():
        raise ValidationError(f"{season.name} has ended.")

    if not order.items:
        raise ValidationError("An order needs at least one person in it.")

    player_ids = [item.player_id for item in order.items]
    if len(set(player_ids)) != len(player_ids):
        raise ValidationError("The same person appears twice in this order.")

    players = {
        player.id: player
        for player in Player.objects.filter(id__in=player_ids).select_related("user")
    }
    missing = sorted(set(player_ids) - set(players))
    if missing:
        raise ValidationError(f"Some players couldn't be found in the DB: {missing}")

    lines = []
    for item in order.items:
        player = players[item.player_id]
        plan = catalog.plan_for(season, item.plan_type)
        if plan is None:
            raise ValidationError(f"{item.plan_type} is not offered for {season.name}.")
        try:
            priced = quote(player, plan)
        except (NotForSale, NeedsGrant) as error:
            raise ValidationError(f"{player.user.get_full_name()}: {error}") from error
        lines.append((player, priced))

    if len(lines) > 1 and any(priced.kind == UPGRADE for _, priced in lines):
        raise ValidationError("Upgrades are bought one person at a time.")

    return season, lines


def create_transaction(
    request: AuthenticatedHttpRequest,
    order: SubscriptionOrderSchema | PlayerRegistrationSchema | TeamRegistrationSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    user = request.user
    ts = round(time.time())
    lines: list[tuple[Player, Quote]] = []

    if isinstance(order, PlayerRegistrationSchema):
        players = Player.objects.filter(id__in=order.player_ids)
        player_ids = {p.id for p in players}
        if len(player_ids) != len(order.player_ids):
            missing_players = set(order.player_ids) - player_ids
            return 422, {
                "message": f"Some players couldn't be found in the DB: {sorted(missing_players)}"
            }

    if isinstance(order, SubscriptionOrderSchema):
        try:
            season, lines = build_subscription_order(order)
        except ValidationError as invalid:
            return 422, {"message": str(invalid)}
        start_date = season.start_date
        end_date = season.end_date
        event = None
        team = None
        # The amount always comes from the plans, never from the client.
        amount = sum(priced.amount for _, priced in lines)
        members = [player for player, _ in lines]
        player_names = _names(members)
        notes: dict[str, int | str] = {
            "user_id": user.id,
            "season_id": season.id,
            "player_ids": str([player.id for player in members]),
            "players": player_names,
            "iu_ids": ", ".join(player.iu_id or "new" for player in members),
        }
        first = members[0]
        receipt = (
            f"{first.iu_id or first.id}:{season.id}:{ts}"
            if len(members) == 1
            else f"group:{season.id}:{ts}"
        )

    elif isinstance(order, TeamRegistrationSchema):
        try:
            event = Event.objects.get(id=order.event_id)
            team = Team.objects.get(id=order.team_id)
        except Event.DoesNotExist:
            return 422, {"message": "Event does not exist!"}
        except Team.DoesNotExist:
            return 422, {"message": "Team does not exist!"}

        if request.user not in team.admins.all():
            return 401, {"message": "Only team admins can register a team to a tournament !"}

        try:
            tournament = Tournament.objects.get(event=event)
        except Tournament.DoesNotExist:
            return 400, {"message": "Tournament does not exist"}

        if order.partial:
            partial_end = (
                event.team_partial_registration_end_date or event.team_registration_end_date
            )
            if not is_today_in_between_dates(event.team_registration_start_date, partial_end):
                return 400, {"message": "Partial team registration has closed!"}
        else:
            full_end = max(
                filter(None, [event.team_late_penalty_end_date, event.team_registration_end_date])
            )
            if not is_today_in_between_dates(event.team_registration_start_date, full_end):
                return 400, {
                    "message": "Team registration has closed, you can't register a team now!"
                }

        if event.series and team not in event.series.teams.all():
            return 400, {
                "message": "Team is not part of the series",
            }

        if event.max_num_teams and len(tournament.teams.all()) >= event.max_num_teams:
            return 400, {"message": "Tournament already has maximum registered teams!"}

        start_date = event.start_date
        end_date = event.end_date
        season = None

        if order.partial:
            amount = event.partial_team_fee
        elif team in tournament.partial_teams.all():
            amount = event.team_fee - event.partial_team_fee
        else:
            amount = event.team_fee

        days_late = 0
        penalty = 0
        if not order.partial:
            days_late, penalty = calculate_late_penalty(
                event.team_registration_end_date,
                event.team_late_penalty,
                event.team_late_penalty_end_date,
            )
        base_amount = amount
        amount += penalty

        notes = {
            "user_id": user.id,
            "team_id": team.id,
            "event_id": event.id,
            "base_amount": str(base_amount),
            "penalty_amount": str(penalty),
            "days_late": str(days_late),
        }
        receipt = f"team:{event.id}:{team.id}:{ts}"

    elif isinstance(order, PlayerRegistrationSchema):
        try:
            team = Team.objects.get(id=order.team_id)
            event = Event.objects.get(id=order.event_id)
            tournament = Tournament.objects.get(event=event)
        except (Event.DoesNotExist, Team.DoesNotExist, Tournament.DoesNotExist):
            return 400, {"message": "Team/Event/Tournament does not exist"}

        if not is_today_in_between_dates(
            from_date=tournament.event.player_registration_start_date,
            to_date=max(
                filter(
                    None,
                    [
                        tournament.event.player_late_penalty_end_date,
                        tournament.event.player_registration_end_date,
                    ],
                )
            ),
        ):
            return 400, {"message": "Rostering has closed, you can't roster players now !"}

        if team not in tournament.teams.all():
            return 400, {"message": f"{team.name} is not registered for ${event.title} !"}

        if request.user not in team.admins.all():
            return 401, {"message": "Only team admins can roster players to the team"}

        if len(players) == 0:
            return 400, {"message": "No players selected !"}

        for player in players:
            is_playing = True
            if event.series:
                can_register, error = can_register_player_to_series_event(
                    event=event, team=team, player=player
                )
                if not can_register and error:
                    return 400, error
                is_playing = is_playing_role(series_role(event, team, player) or Role.DEFAULT)

            subscription_error = eligibility.check(player, event, is_playing=is_playing)
            if subscription_error is not None:
                return 400, subscription_error

            if Registration.objects.filter(event=event, player=player).exists():
                return 400, {
                    "message": f"Player - {player.user.get_full_name()} already registered for this event in another team !"
                }

        start_date = event.start_date
        end_date = event.end_date
        season = None

        days_late, per_player_penalty = calculate_late_penalty(
            event.player_registration_end_date,
            event.player_late_penalty,
            event.player_late_penalty_end_date,
        )
        base_amount = event.player_fee * len(players)
        penalty = per_player_penalty * len(players)
        amount = base_amount + penalty

        player_names = ", ".join(sorted([player.user.get_full_name() for player in players]))
        if len(player_names) > razorpay.RAZORPAY_NOTES_MAX:
            player_names = player_names[:500] + "..."

        notes = {
            "user_id": user.id,
            "team_id": team.id,
            "event_id": event.id,
            "player_ids": str(player_ids),
            "players": player_names,
            "base_amount": str(base_amount),
            "penalty_amount": str(penalty),
            "days_late": str(days_late),
        }
        receipt = f"player:{event.id}:{team.id}:{ts}"

    else:
        # NOTE: We should never be here, thanks to request validation!
        pass

    data = razorpay.create_order(amount, receipt=receipt, notes=notes)
    if data is None:
        return 502, "Failed to connect to Razorpay."

    data.update(
        {
            "start_date": start_date,
            "end_date": end_date,
            "user": user,
            # Subscription lines are written below, each with what it bought.
            "players": players if isinstance(order, PlayerRegistrationSchema) else [],
            "event": event,
            "season": season,
            "team": team,
            "type": RazorpayTransaction.TransactionTypeChoices.PARTIAL_TEAM_REGISTRATION
            if isinstance(order, TeamRegistrationSchema) and order.partial
            else RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION
            if isinstance(order, TeamRegistrationSchema)
            else RazorpayTransaction.TransactionTypeChoices.PLAYER_REGISTRATION
            if isinstance(order, PlayerRegistrationSchema)
            else RazorpayTransaction.TransactionTypeChoices.ANNUAL_SUBSCRIPTION,
        }
    )
    with db_transaction.atomic():
        transaction = RazorpayTransaction.create_from_order_data(data)
        RazorpayTransactionPlayer.objects.bulk_create(
            RazorpayTransactionPlayer(
                transaction=transaction, player=player, plan=priced.plan, amount=priced.amount
            )
            for player, priced in lines
        )

    transaction_user_name = user.get_full_name()
    if isinstance(order, TeamRegistrationSchema):
        description = f"Team registration payment by {transaction_user_name} for {team.name if team is not None else ''}, event: {event.title if event is not None else ''}"
    elif isinstance(order, PlayerRegistrationSchema):
        description = f"Player registration payment by {transaction_user_name} for {player_names}, event: {event.title if event is not None else ''}"
    elif len(lines) == 1:
        member, priced = lines[0]
        description = f"{priced.plan.type.name} subscription for {member.user.get_full_name()}, {priced.plan.season.name}"
    else:
        description = f"Subscription group payment by {transaction_user_name} for {player_names}"
    if len(description) > razorpay.RAZORPAY_DESCRIPTION_MAX:
        description = description[:250] + "..."
    data.update(
        {
            "name": settings.APP_NAME,
            "image": settings.LOGO_URL,
            "description": description,
            "prefill": {"name": user.get_full_name(), "email": user.email, "contact": user.phone},
        }
    )

    return 200, data


def apply_transaction(transaction: RazorpayTransaction, notify: bool = True) -> None:
    """Give the buyer what a captured payment bought.

    Every payment route ends here, so the one guard below is the only place
    that decides whether an order is settled enough to act on. A refunded
    order never is, however many times Razorpay reports it as captured.

    `notify` off skips the confirmation emails, for a bulk historical resync.
    """
    if transaction.status != RazorpayTransaction.TransactionStatusChoices.COMPLETED:
        return

    kinds = RazorpayTransaction.TransactionTypeChoices
    if transaction.type == kinds.ANNUAL_SUBSCRIPTION:
        fulfil(transaction, notify=notify)
    elif transaction.type == kinds.TEAM_REGISTRATION:
        update_transaction_team_registration(transaction)
    elif transaction.type == kinds.PLAYER_REGISTRATION:
        update_transaction_player_registrations(transaction)
    elif transaction.type == kinds.PARTIAL_TEAM_REGISTRATION:
        update_transaction_partial_team_registration(transaction)
    elif transaction.type == kinds.FORM_PAYMENT:
        # Lazy import to avoid a transaction <-> forms import cycle.
        from server.forms.utils import mark_form_response_paid

        mark_form_response_paid(transaction)


def update_transaction_team_registration(
    transaction: RazorpayTransaction,
) -> None:
    try:
        tournament = Tournament.objects.get(event=transaction.event)
    except Tournament.DoesNotExist:
        return

    if transaction.team is not None:
        tournament.partial_teams.remove(transaction.team)
        tournament.teams.add(transaction.team)


def update_transaction_partial_team_registration(
    transaction: RazorpayTransaction,
) -> None:
    try:
        tournament = Tournament.objects.get(event=transaction.event)
    except Tournament.DoesNotExist:
        return

    if transaction.team is not None:
        tournament.partial_teams.add(transaction.team)


def update_transaction_player_registrations(
    transaction: RazorpayTransaction,
) -> None:
    event = transaction.event
    team = transaction.team
    for player in transaction.players.all():
        role: str = Role.DEFAULT
        if event is not None and team is not None and event.series:
            role = series_role(event, team, player) or Role.DEFAULT
        try:
            registration = Registration(
                event=event,
                team=team,
                player=player,
                is_playing=is_playing_role(role),
                role=role,
            )

            registration.save()
        except IntegrityError:
            pass


def list_transactions_by_type(
    user: User, payment_type: PaymentGateway, user_only: bool = True, only_invalid: bool = False
) -> QuerySet[Model]:
    transaction_classes = {
        PaymentGateway.MANUAL: ManualTransaction,
        PaymentGateway.RAZORPAY: RazorpayTransaction,
        PaymentGateway.PHONEPE: PhonePeTransaction,
    }
    Cls = transaction_classes[payment_type]  # noqa: N806
    order_by = (
        "-payment_date"
        if payment_type in {PaymentGateway.MANUAL, PaymentGateway.RAZORPAY}
        else "-transaction_date"
    )

    if not user_only and user.is_staff:
        transactions = Cls.objects.filter(validated=False) if only_invalid else Cls.objects.all()

    else:
        # Get ids of all associated players of a user (player + wards)
        ward_ids = set(user.guardianship_set.values_list("player_id", flat=True))
        player_id = set(Player.objects.filter(user=user).values_list("id", flat=True))
        player_ids = ward_ids.union(player_id)

        query = Q(user=user) | Q(players__in=player_ids)
        transactions = Cls.objects.filter(query)
        if only_invalid:
            transactions = transactions.filter(validated=False)

    return transactions.distinct().order_by(order_by)

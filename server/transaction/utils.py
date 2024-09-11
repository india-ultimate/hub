import time
from typing import Any

from django.conf import settings
from django.db.models import Model, Q, QuerySet

from server.constants import EVENT_MEMBERSHIP_AMOUNT
from server.core.models import Player, User
from server.membership.models import Membership
from server.season.models import Season
from server.tournament.models import Event
from server.types import message_response

from .client import phonepe, razorpay
from .models import (
    AuthenticatedHttpRequest,
    ManualTransaction,
    PaymentGateway,
    PhonePeTransaction,
    RazorpayTransaction,
)
from .schema import AnnualMembershipSchema, EventMembershipSchema, GroupMembershipSchema


def create_transaction(
    request: AuthenticatedHttpRequest,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
    gateway: PaymentGateway,
    transaction_id: str | None = None,
) -> tuple[int, str | message_response | dict[str, Any]]:
    if isinstance(order, GroupMembershipSchema):
        group_payment = True
        players = Player.objects.filter(id__in=order.player_ids)
        player_ids = {p.id for p in players}
        if len(player_ids) != len(order.player_ids):
            missing_players = set(order.player_ids) - player_ids
            return 422, {
                "message": f"Some players couldn't be found in the DB: {sorted(missing_players)}"
            }

    else:
        group_payment = False
        try:
            player = Player.objects.get(id=order.player_id)
        except Player.DoesNotExist:
            return 422, {"message": "Player does not exist!"}

    if isinstance(order, GroupMembershipSchema | AnnualMembershipSchema):
        try:
            season = Season.objects.get(id=order.season_id)
        except Season.DoesNotExist:
            return 422, {"message": "Season does not exist!"}
        start_date = season.start_date
        end_date = season.end_date
        is_annual = True
        event = None
        amount = (
            sum(
                (
                    season.sponsored_annual_membership_amount
                    if player.sponsored
                    else season.annual_membership_amount
                )
                for player in players
            )
            if isinstance(order, GroupMembershipSchema)
            else (
                season.sponsored_annual_membership_amount
                if player.sponsored
                else season.annual_membership_amount
            )
        )

    elif isinstance(order, EventMembershipSchema):
        try:
            event = Event.objects.get(id=order.event_id)
        except Event.DoesNotExist:
            return 422, {"message": "Event does not exist!"}

        start_date = event.start_date
        end_date = event.end_date
        is_annual = False
        amount = EVENT_MEMBERSHIP_AMOUNT
        season = None

    else:
        # NOTE: We should never be here, thanks to request validation!
        pass

    user = request.user
    ts = round(time.time())
    membership_defaults = {
        "is_annual": is_annual,
        "start_date": start_date,
        "end_date": end_date,
        "event": event,
        "season": season,
    }
    if group_payment:
        player_names = ", ".join(sorted([player.user.get_full_name() for player in players]))
        if len(player_names) > razorpay.RAZORPAY_NOTES_MAX:
            player_names = player_names[:500] + "..."
        notes = {
            "user_id": user.id,
            "player_ids": str(player_ids),
            "players": player_names,
        }
        receipt = f"group:{start_date}:{ts}"
        for player in players:
            Membership.objects.get_or_create(player=player, defaults=membership_defaults)
    else:
        membership, _ = Membership.objects.get_or_create(
            player=player,
            defaults=membership_defaults,
        )
        notes = {
            "user_id": user.id,
            "player_id": player.id,
            "membership_id": membership.id,
        }
        receipt = f"{membership.membership_number}:{start_date}:{ts}"

    if gateway == PaymentGateway.RAZORPAY:
        data = razorpay.create_order(amount, receipt=receipt, notes=notes)
        if data is None:
            return 502, "Failed to connect to Razorpay."
    elif gateway == PaymentGateway.PHONEPE:
        host = f"{request.scheme}://{request.get_host()}"
        next_url = "/membership/group" if group_payment else f"/membership/{player.id}"
        data = phonepe.initiate_payment(amount, user, host, next_url)
        if data is None:
            return 502, "Failed to connect to PhonePe."
    else:
        data = {"amount": amount, "currency": "INR", "transaction_id": transaction_id}

    data.update(
        {
            "start_date": start_date,
            "end_date": end_date,
            "user": user,
            "players": [player] if not group_payment else players,
            "event": event,
            "season": season,
        }
    )
    if gateway == PaymentGateway.RAZORPAY:
        RazorpayTransaction.create_from_order_data(data)
        transaction_user_name = user.get_full_name()
        description = (
            f"Membership for {player.user.get_full_name()}"
            if not group_payment
            else f"Membership group payment by {transaction_user_name} for {player_names}"
        )
        if len(description) > razorpay.RAZORPAY_DESCRIPTION_MAX:
            description = description[:250] + "..."
        extra_data = {
            "name": settings.APP_NAME,
            "image": settings.LOGO_URL,
            "description": description,
            "prefill": {"name": user.get_full_name(), "email": user.email, "contact": user.phone},
        }
        data.update(extra_data)
    elif gateway == PaymentGateway.PHONEPE:
        PhonePeTransaction.create_from_order_data(data)
    elif gateway == PaymentGateway.MANUAL:
        ManualTransaction.create_from_order_data(data)
        memberships = Membership.objects.filter(
            player__in=player_ids if group_payment else [player.id]
        )
        memberships.update(is_active=True, start_date=start_date, end_date=end_date)
    else:
        # We shouldn't get here, because enum
        pass

    return 200, data


def update_transaction_player_memberships(
    transaction: RazorpayTransaction | PhonePeTransaction,
) -> None:
    membership_defaults = {
        "start_date": transaction.start_date,
        "end_date": transaction.end_date,
        "event": transaction.event,
        "season": transaction.season,
        "is_active": True,
    }
    for player in transaction.players.all():
        membership, created = Membership.objects.get_or_create(
            player=player, defaults=membership_defaults
        )
        if not created:
            for key, value in membership_defaults.items():
                setattr(membership, key, value)
            membership.save()


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

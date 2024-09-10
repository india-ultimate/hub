import contextlib
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.utils import IntegrityError
from prettytable import PrettyTable

from server.core.models import (
    Guardianship,
    Player,
    User,
)
from server.membership.models import Membership
from server.tournament.models import UCRegistration
from server.transaction.models import ManualTransaction, PhonePeTransaction, RazorpayTransaction


def calculate_completeness_score(username: str) -> tuple[float, dict[str, Any]]:
    # Define fields to consider for completeness score calculation
    fields_to_check = [
        "player_profile",
        "player_profile__date_of_birth",
        "player_profile__ultimate_central_id",
        "player_profile__membership__start_date",
        "player_profile__membership__end_date",
        "player_profile__membership__is_active",
        "player_profile__accreditation__wfdf_id",
        "player_profile__accreditation__level",
        "player_profile__accreditation__date",
        "player_profile__vaccination__name",
        "player_profile__vaccination__is_vaccinated",
        "player_profile__vaccination__certificate",
        "player_profile__membership__waiver_signed_by",
        "player_profile__membership__waiver_signed_at",
    ]

    # Retrieve data from the database for the specific user
    user_data = User.objects.filter(username=username).values(*fields_to_check).first()
    if user_data is None:
        user_data = {key: None for key in fields_to_check}
        return 0.0, user_data

    uc_id = user_data["player_profile__ultimate_central_id"]
    if uc_id:
        # Also a proxy for ultimate_central_id being a valid one
        # We'd like to keep the UC ID with more registrations
        registrations = UCRegistration.objects.filter(person__id=uc_id).count()
    user_data["registrations"] = registrations if uc_id else 0

    player_id = user_data["player_profile"]
    if player_id is not None:
        transactions = (
            ManualTransaction.objects.filter(players__in=[player_id]).count()
            + PhonePeTransaction.objects.filter(players__in=[player_id]).count()
            + RazorpayTransaction.objects.filter(players__in=[player_id]).count()
        )
    user_data["transactions"] = transactions if player_id else 0

    total_fields = len(user_data)
    completed_fields = sum(bool(value) for key, value in user_data.items())
    completeness_score = (completed_fields / total_fields) * 100
    return completeness_score, user_data


def compare_users(usernames: list[str]) -> dict[str, Any]:
    data = {}
    for username in usernames:
        completeness_score, info = calculate_completeness_score(username)
        data[username] = dict(score=completeness_score, **info)

    pt = PrettyTable()
    pt.field_names = ["User Data", *usernames]
    user_fields = {
        "WFDF ID": "player_profile__accreditation__wfdf_id",
        "Vaccination": "player_profile__vaccination__name",
        "Membership": None,
        "UC Profile": "player_profile__ultimate_central_id",
        "Registrations": "registrations",
        "Transactions": "transactions",
        "Player Profile": "player_profile",
        "Completeness": "score",
    }
    pt.align["User Data"] = "l"
    for label, attr in user_fields.items():
        if label == "Membership":
            start = "player_profile__membership__start_date"
            end = "player_profile__membership__end_date"
            active = "player_profile__membership__is_active"
            row_info = [
                f"{data[u][start]}-{data[u][end]}" if data[u][active] else "--" for u in usernames
            ]
        else:
            row_info = [data[u].get(attr, "--") for u in usernames if attr]
        divider = label == "Player Profile"
        pt.add_row([label, *row_info], divider=divider)
    print(pt)
    return data


def find_duplicate_email_usernames() -> list[list[str]]:
    users = dict(User.objects.values_list("username", "email"))
    emails_to_usernames: dict[str, list[str]] = {}
    for username, email in users.items():
        email_ = email.lower().strip()
        if email_ in emails_to_usernames:
            emails_to_usernames[email_].append(username)
        else:
            emails_to_usernames[email_] = [username]

    return [usernames for usernames in emails_to_usernames.values() if len(usernames) > 1]


class Command(BaseCommand):
    help = "Command to merge accounts"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("usernames", nargs="*", help="Usernames of accounts to merge.")

    def handle(self, *args: Any, **options: Any) -> None:
        usernames = options["usernames"]
        if len(usernames) == 2:  # noqa: PLR2004
            self.merge_users(usernames)
        elif len(usernames) == 0:
            duplicates = find_duplicate_email_usernames()
            for usernames in duplicates:
                self.stdout.write(self.style.NOTICE(f"Merging usernames: {','.join(usernames)}"))
                self.merge_users(usernames)
            if not duplicates:
                self.stdout.write(self.style.NOTICE("No duplicate emails found"))
        else:
            raise CommandError("Too many args.")

    def merge_users(self, usernames: list[str]) -> None:
        user_data = compare_users(usernames)
        # NOTE: We could sort the usernames by score to keep the account with
        # the higher score, but it doesn't seem worth doing that. We could just
        # keep the email ID supplied first.
        # usernames = sorted(user_data, key=lambda e: user_data[e]["score"], reverse=True)
        n = len(usernames)
        if n > 2:  # noqa: PLR2004
            self.stdout.write(
                self.style.ERROR(f"Cannot merge {n} usernames. Try manually 2 at a time...")
            )
            return

        username1, username2 = usernames
        try:
            user1 = User.objects.get(username=username1)
            user2 = User.objects.get(username=username2)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("Ensure both users are valid"))
            return

        self.stdout.write(self.style.NOTICE(f"Merging account {username2} into {username1} ..."))

        try:
            player = user1.player_profile
            player2 = user2.player_profile
        except Player.DoesNotExist:
            if not hasattr(user2, "player"):
                self.clean_users(user1, user2)
                return
            # If user1's player doesn't exist
            player2.user = user1
            player2.save(update_fields=["user"])
            self.clean_users(user1, user2)
            return

        # Memberships
        try:
            membership2 = player2.membership
        except Membership.DoesNotExist:
            pass
        else:
            if membership2.is_active:
                if hasattr(player, "membership"):
                    if player.membership.is_active and (
                        player.membership.start_date != membership2.start_date
                        or player.membership.end_date != membership2.end_date
                    ):
                        raise CommandError("Cannot merge with different membership dates")
                    # if not hasattr(membership2, 'waiver_signed_by') and hasattr(player.membership, 'waiver_signed_by'):
                    #     membership2.waiver_signed_by =

                    player.membership.delete()

                membership2.player = player
                membership2.save(update_fields=["player"])
                self.stdout.write(self.style.NOTICE("Membership transferred..."))

        # Guardianships
        for guardianship in Guardianship.objects.filter(user=user2):
            guardianship.user = user1
            guardianship.save(update_fields=["user"])

        for guardianship in Guardianship.objects.filter(player=player2):
            guardianship.player = player
            with contextlib.suppress(IntegrityError):
                guardianship.save(update_fields=["player"])

        # Transactions
        transactions = (
            list(player2.manualtransaction_set.all())
            + list(player2.phonepetransaction_set.all())
            + list(player2.razorpaytransaction_set.all())
        )
        for transaction in transactions:
            if transaction.user == user2:
                transaction.user = user1
                transaction.save(update_fields=["user"])

            if transaction.players.filter(id=player2.id).first():
                transaction.players.remove(player2)
                transaction.players.add(player)

        # UC id
        if (
            user_data[username2]["registrations"] > user_data[username1]["registrations"]
            or player.ultimate_central_id is None
        ):
            player.ultimate_central_id = player2.ultimate_central_id
            player2.ultimate_central_id = None
            player2.save(update_fields=["ultimate_central_id"])
            player.save(update_fields=["ultimate_central_id"])
            self.stdout.write(self.style.NOTICE("Copied Ultimate Central ID..."))

        # Accreditation
        if not hasattr(player, "accreditation") and hasattr(player2, "accreditation"):
            accreditation = player2.accreditation
            accreditation.player = player
            accreditation.save(update_fields=["player"])
            self.stdout.write(self.style.NOTICE("Accreditation copied..."))

        # Vaccination
        if not hasattr(player, "vaccination") and hasattr(player2, "vaccination"):
            vaccination = player2.vaccination
            vaccination.player = player
            vaccination.save(update_fields=["player"])
            self.stdout.write(self.style.NOTICE("Vaccination copied..."))

        self.clean_users(user1, user2)

    def clean_users(self, user1: User, user2: User) -> None:
        username = user2.username
        user2.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {username}"))
        user1.username = user1.email = user1.email.lower()
        user1.save(update_fields=["email", "username"])

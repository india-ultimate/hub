from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from prettytable import PrettyTable

from server.core.models import User
from server.duplicates import review
from server.duplicates.merge import MergeBlockedError, merge_accounts

MIN_ACCOUNTS = 2


def compare(primary: User, duplicates: list[User]) -> None:
    """Side by side, so the account being kept is an informed choice."""
    accounts = [primary, *duplicates]
    table = PrettyTable()
    table.field_names = ["", *[user.username for user in accounts]]
    table.align[""] = "l"
    table.add_row(["Keeping", *["yes" if user == primary else "" for user in accounts]])
    lines = review.compare(primary, duplicates)
    for line in lines:
        table.add_row([f"{line.label} *" if line.differs else line.label, *line.values])
    print(table)
    if any(line.differs for line in lines):
        print("* the accounts disagree about who this is")


class Command(BaseCommand):
    help = (
        "Merge accounts into the first one given. Reports unless --apply. "
        "The merged accounts' addresses then sign in to the kept one."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("usernames", nargs="*", help="The account to keep comes first.")
        parser.add_argument("--apply", action="store_true", help="Perform the merge.")

    def handle(self, *args: Any, **options: Any) -> None:
        usernames = options["usernames"]
        if len(usernames) < MIN_ACCOUNTS:
            raise CommandError(
                "Give the account to keep first, then the ones to merge into it. "
                "Use find_duplicate_accounts to see which accounts look duplicated."
            )

        try:
            primary = User.objects.get(username=usernames[0])
            duplicates = [User.objects.get(username=name) for name in usernames[1:]]
        except User.DoesNotExist as missing:
            raise CommandError(f"No such account: {missing}") from missing

        compare(primary, duplicates)

        try:
            plan = merge_accounts(primary, duplicates, dry_run=not options["apply"])
        except MergeBlockedError as blocked:
            raise CommandError(f"Cannot merge: {', '.join(blocked.args[0])}") from blocked

        for move in plan.moves:
            lost = ""
            if move.collided:
                lost = f", {move.collided} clash and lose a row"
                if move.primary_loses:
                    lost += f" ({move.primary_loses} of them {primary.username}'s own)"
            self.stdout.write(f"  {move.label}: {move.moved}{lost}")

        if options["apply"]:
            self.stdout.write(
                self.style.SUCCESS(f"Merged into {primary.username}, {plan.rows_moved} rows moved")
            )
        else:
            self.stdout.write(
                self.style.NOTICE(f"Would move {plan.rows_moved} rows. Re-run with --apply.")
            )

import csv
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.duplicates.clusters import close_finished, create_clusters
from server.duplicates.detect import Cluster, find_clusters

CSV_COLUMNS = [
    "cluster",
    "rules",
    "blockers",
    "user_id",
    "player_id",
    "email",
    "username",
    "phone",
    "date_of_birth",
    "ultimate_central_id",
    "last_login",
]


def csv_rows(clusters: list[Cluster]) -> list[dict[str, Any]]:
    return [
        {
            "cluster": index,
            "rules": " ".join(sorted(cluster.rules)),
            "blockers": " ".join(cluster.blockers),
            "user_id": member.user_id,
            "player_id": member.player_id,
            "email": member.email,
            "username": member.username,
            "phone": member.phone,
            "date_of_birth": member.date_of_birth.isoformat(),
            "ultimate_central_id": member.ultimate_central_id or "",
            "last_login": member.last_login.isoformat() if member.last_login else "",
        }
        for index, cluster in enumerate(clusters, start=1)
        for member in cluster.members
    ]


class Command(BaseCommand):
    help = "Report accounts that look like duplicates. Writes nothing."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--csv", type=str, help="Write one row per account to this path.")
        parser.add_argument(
            "--create", action="store_true", help="Save mergeable clusters for notifying."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["create"]:
            # First, and whatever detection finds: a day with no new
            # duplicates is exactly when a group left open would otherwise
            # never be looked at again. create_clusters sweeps too, which
            # finds nothing left by then.
            closed = close_finished()
            self.stdout.write(f"Closed {closed} group(s) with nothing left to merge")

        clusters = find_clusters()
        if not clusters:
            self.stdout.write(self.style.NOTICE("No duplicate accounts found"))
            return

        accounts = sum(len(c.members) for c in clusters)
        mergeable = [c for c in clusters if c.is_mergeable]
        unreachable = sum(1 for c in clusters for m in c.members if not m.has_deliverable_email)

        self.stdout.write(f"Clusters:              {len(clusters)}")
        self.stdout.write(f"Accounts involved:     {accounts}")
        self.stdout.write(f"Would be merged away:  {accounts - len(clusters)}")
        self.stdout.write(f"Largest cluster:       {max(len(c.members) for c in clusters)}")
        self.stdout.write(f"Mergeable clusters:    {len(mergeable)}")
        self.stdout.write(f"Blocked clusters:      {len(clusters) - len(mergeable)}")
        self.stdout.write(f"Accounts with no email:{unreachable}")

        for reason in sorted({b for c in clusters for b in c.blockers}):
            blocked = sum(1 for c in clusters if reason in c.blockers)
            self.stdout.write(f"  blocked by {reason}: {blocked}")

        if options["create"]:
            created = create_clusters(clusters)
            self.stdout.write(self.style.SUCCESS(f"Saved {len(created)} new clusters"))

        path = options["csv"]
        if path:
            with Path(path).open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                writer.writerows(csv_rows(clusters))
            self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))

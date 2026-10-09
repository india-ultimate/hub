"""Copy the uploaded files on this machine's disk to Cloudinary, once.

Copies what the database or content points at; skips vaccination
certificates (archived instead), college IDs past their 30 days, and files
nothing points at. Safe to re-run: a file already there at the same size is
skipped. Each copy is checked by fetching its Cloudinary URL.
"""

import datetime
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cloudinary.api
import cloudinary.exceptions
import cloudinary.uploader
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from server.core.models import Accreditation, CollegeId, Team
from server.storage import kinds
from server.tournament.models import Tournament
from server.utils import today

HTTP_OK = 200
# Not in the database, but linked from rich text and staff emails.
FOLDERS = ("ckeditor_uploads", "contact-form-attachments")


def referenced_names() -> Iterator[str]:
    yield from Team.objects.exclude(image="").values_list("image", flat=True)
    for field in ("logo_light", "logo_dark"):
        yield from Tournament.objects.exclude(**{field: ""}).values_list(field, flat=True)
    yield from Accreditation.objects.exclude(certificate="").values_list("certificate", flat=True)
    cutoff = today() - datetime.timedelta(days=30)
    for front, back in CollegeId.objects.filter(expiry__gte=cutoff).values_list(
        "card_front", "card_back"
    ):
        yield from (n for n in (front, back) if n)


def folder_names(root: Path) -> Iterator[str]:
    for folder in FOLDERS:
        for path in sorted((root / folder).rglob("*")):
            if path.is_file():
                yield str(path.relative_to(root))


class Command(BaseCommand):
    help = "Copy uploaded files from this machine's disk to Cloudinary"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="List and size; upload nothing")

    def already_there(self, name: str, size: int) -> bool:
        try:
            found = cloudinary.api.resource(
                kinds.public_id(name), resource_type=kinds.resource_type(name)
            )
        except cloudinary.exceptions.NotFound:
            return False
        return int(found.get("bytes", -1)) == size

    def copy(self, path: Path, name: str) -> None:
        with path.open("rb") as f:
            cloudinary.uploader.upload(
                f,
                public_id=kinds.public_id(name),
                resource_type=kinds.resource_type(name),
                overwrite=True,  # a half-finished earlier upload is replaced
                unique_filename=False,
                use_filename=False,
            )
        response = requests.head(kinds.url(name), timeout=30, allow_redirects=True)
        if response.status_code != HTTP_OK:
            raise RuntimeError(f"Cloudinary serves it as {response.status_code}")

    def handle(self, *args: Any, **options: Any) -> None:
        root = Path(settings.MEDIA_ROOT)
        names = sorted(set(referenced_names()) | set(folder_names(root)))
        counts: Counter[tuple[str, str]] = Counter()
        sizes: Counter[str] = Counter()
        missing: list[str] = []
        failed: list[str] = []
        for name in names:
            folder = name.split("/", 1)[0]
            path = root / name
            if not path.is_file():
                missing.append(name)
                continue
            size = path.stat().st_size
            if self.already_there(name, size):
                counts[(folder, "skipped")] += 1
                continue
            counts[(folder, "to copy")] += 1
            sizes[folder] += size
            if options["dry_run"]:
                continue
            try:
                self.copy(path, name)
                counts[(folder, "copied")] += 1
            except Exception as error:  # one bad file mustn't stop the rest
                counts[(folder, "failed")] += 1
                failed.append(f"{name}: {error}")
        for folder in sorted({f for f, _ in counts} | set(sizes)):
            parts = [
                f"{state} {counts[(folder, state)]}"
                for state in ("to copy", "copied", "skipped", "failed")
                if counts[(folder, state)]
            ]
            self.stdout.write(f"{folder}: {', '.join(parts)} ({sizes[folder] / 1e6:.1f} MB)")
        if missing:
            self.stdout.write(f"Missing on disk ({len(missing)}):")
            for name in missing:
                self.stdout.write(f"  {name}")
        if failed:
            self.stdout.write(f"{len(failed)} failed:")
            for line in failed:
                self.stdout.write(f"  {line}")
            sys.exit(1)

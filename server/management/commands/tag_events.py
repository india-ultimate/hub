import csv
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import models, transaction

from server.tournament.models import Event

BOOLEANS = {"true": True, "false": False, "": None}
# Validation looks only at the tags; the rest of an event is as it was.
NOT_TAGS = [field.name for field in Event._meta.fields if field.name not in Event.TAG_FIELDS]


class Command(BaseCommand):
    # The reviewed sheet of past events is server/tournament/data/event_tags.csv.
    help = (
        "Tag events from a CSV with id, title and a column per tag. Every row is "
        "checked first: if any is wrong, nothing is saved."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=Path, help="Path to the CSV file")
        parser.add_argument(
            "--dry-run", action="store_true", help="Check the file and report, saving nothing"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        with open(options["csv_file"], encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        events = Event.objects.in_bulk([int(row["id"]) for row in rows])

        changes, errors = [], []
        for row in rows:
            try:
                event, fields = self.tagged(events.get(int(row["id"])), row)
            except ValidationError as error:
                errors.append(f"{row['id']} ({row['title']}): {'; '.join(error.messages)}")
                continue
            if fields:
                changes.append((event, fields))
        if errors:
            raise CommandError("Nothing saved. Fix these rows:\n" + "\n".join(errors))

        if not options["dry_run"]:
            with transaction.atomic():
                for event, fields in changes:
                    event.save(update_fields=fields)
        verb = "Would tag" if options["dry_run"] else "Tagged"
        noun = "event" if len(changes) == 1 else "events"
        self.stdout.write(
            f"{verb} {len(changes)} {noun}; the other {len(rows) - len(changes)} were up to date."
        )

    def tagged(self, event: Event | None, row: dict[str, str]) -> tuple[Event, list[str]]:
        """The event with the row's tags set, and the fields that changed."""
        if event is None:
            raise ValidationError("no event has this id")
        if event.title.strip() != row["title"].strip():
            raise ValidationError(f"the event is called {event.title.strip()!r}")
        changed = []
        for name in Event.TAG_FIELDS:
            raw = row[name].strip()
            if isinstance(Event._meta.get_field(name), models.BooleanField):
                if raw.lower() not in BOOLEANS:
                    raise ValidationError(f"{name} is {raw!r}, not true, false or blank")
                value: Any = BOOLEANS[raw.lower()]
            else:
                value = raw or None
            if getattr(event, name) != value:
                setattr(event, name, value)
                changed.append(name)
        # The model checks each value against its choices, and the rules
        # between fields (a series event must be sanctioned).
        event.full_clean(exclude=NOT_TAGS, validate_unique=False, validate_constraints=False)
        return event, changed

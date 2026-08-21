"""Find-and-replace across tournament rules."""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from server.tournament.models import Tournament


class Command(BaseCommand):
    help = (
        "Replace text in tournament rules. Use --find-file/--replace-file for "
        "multi-line text. Omit --replace to delete the matched text."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--find", help="Text to look for")
        parser.add_argument("--find-file", help="File holding the text to look for")
        parser.add_argument("--replace", default=None, help="Replacement (default: delete)")
        parser.add_argument("--replace-file", help="File holding the replacement")
        parser.add_argument(
            "--tournament",
            type=int,
            action="append",
            dest="tournaments",
            help="Limit to this tournament id; repeatable (default: all)",
        )
        parser.add_argument("--count", type=int, default=0, help="Max replacements per tournament")
        parser.add_argument("--dry-run", action="store_true", help="Report without saving")

    def handle(self, *args: Any, **options: Any) -> None:
        find = self._text(options["find"], options["find_file"], "--find")
        if not find:
            raise CommandError("--find or --find-file is required")
        replace = self._text(options["replace"], options["replace_file"], "--replace") or ""

        rows = Tournament.objects.exclude(rules__isnull=True).exclude(rules="")
        if options["tournaments"]:
            rows = rows.filter(id__in=options["tournaments"])

        changed = 0
        for tournament in rows:
            rules = tournament.rules or ""
            if find not in rules:
                continue
            updated = rules.replace(find, replace, options["count"] or -1)
            if updated == rules:
                continue
            changed += 1
            title = tournament.event.title
            if options["dry_run"]:
                self.stdout.write(f"  would change: {title} (id {tournament.id})")
                continue
            tournament.rules = updated
            tournament.save(update_fields=["rules"])
            self.stdout.write(f"  changed: {title} (id {tournament.id})")

        verb = "would change" if options["dry_run"] else "changed"
        style = self.style.NOTICE if options["dry_run"] or not changed else self.style.SUCCESS
        self.stdout.write(style(f"{verb} {changed} tournament(s)"))

    @staticmethod
    def _text(literal: str | None, path: str | None, flag: str) -> str | None:
        if literal is not None and path:
            raise CommandError(f"Pass {flag} or {flag}-file, not both")
        if path:
            file = Path(path)
            if not file.is_file():
                raise CommandError(f"No such file: {path}")
            return file.read_text(encoding="utf-8")
        return literal

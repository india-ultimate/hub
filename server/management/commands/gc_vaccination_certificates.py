from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from server.models import Vaccination


class Command(BaseCommand):
    help = "GC vaccination certificate files not referenced in the DB"

    def handle(self, *args: Any, **options: Any) -> None:
        all_certificates = set(settings.MEDIA_ROOT.glob("vaccination_certificates/*"))
        certificates = set(
            Vaccination.objects.exclude(certificate="").values_list("certificate", flat=True)
        )

        gc_files = {
            path
            for path in all_certificates
            if str(path.relative_to(settings.MEDIA_ROOT)) not in certificates
        }
        n = len(gc_files)

        print(f"Found {n} files to GC.")
        for path in gc_files:
            path.unlink()
        print(f"GC'd {n} certificate files not referred from the DB.")

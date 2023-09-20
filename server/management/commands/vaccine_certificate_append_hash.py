from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string

from server.models import Vaccination


class Command(BaseCommand):
    help = "Append hash to vaccination filenames"

    def handle(self, *args: Any, **options: Any) -> None:
        for vaccination in Vaccination.objects.exclude(certificate=""):
            path = Path(vaccination.certificate.name)
            abspath = Path(vaccination.certificate.path)
            new_name = f"{path.stem}-{get_random_string(12)}{path.suffix}"
            abspath.rename(abspath.with_name(new_name))
            vaccination.certificate = str(path.with_name(new_name))
            vaccination.save(update_fields=["certificate"])

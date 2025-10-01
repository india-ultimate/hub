from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from server.task.models import Task


class Command(BaseCommand):
    help = "Clean up old tasks that are more than a week old"

    def handle(self, *args: Any, **options: Any) -> None:
        cutoff_date = timezone.now() - timedelta(days=7)

        completed_tasks = Task.objects.filter(completed_at__lt=cutoff_date)
        failed_tasks = Task.objects.filter(failed_at__lt=cutoff_date)

        completed_count = completed_tasks.count()
        failed_count = failed_tasks.count()

        completed_tasks.delete()
        failed_tasks.delete()

        total_deleted = completed_count + failed_count

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {total_deleted} old tasks "
                f"({completed_count} completed, {failed_count} failed)"
            )
        )

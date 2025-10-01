"""
Management command to run the task queue worker.

Usage:
    python manage.py run_task_worker [--sleep-seconds 5]
"""

import sys
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from server.task.manager import TaskManager


class Command(BaseCommand):
    help = "Run the background task queue worker"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--sleep-seconds",
            type=int,
            default=30,
            help="Number of seconds to sleep when queue is empty (default: 30)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        sleep_seconds = options["sleep_seconds"]

        self.stdout.write(self.style.SUCCESS("Started task queue worker 🏗️"))
        self.stdout.write(f"Sleep interval when idle: {sleep_seconds} seconds")

        try:
            while True:
                task = TaskManager.get_next_task()

                if not task:
                    current_time = timezone.now().strftime("%Y-%m-%d %H:%M:%S %Z")
                    self.stdout.write(
                        f"{current_time}: No tasks in queue. Sleeping for {sleep_seconds} seconds 💤"
                    )
                    time.sleep(sleep_seconds)
                    continue

                # Run the task
                task.run_task()

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nStopping task queue worker..."))
            sys.exit(0)

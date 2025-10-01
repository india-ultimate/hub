"""
Task Queue Manager
"""

from typing import Any

from django.db import transaction
from django.utils import timezone

from server.task.models import Task


class TaskManager:
    """
    Manages task queue operations: adding, fetching, and processing tasks.
    """

    @staticmethod
    def add_task(
        task_type: str,
        data: dict[str, Any],
    ) -> Task:
        """
        Add a new task to the queue.

        :param task_type: Type of task (e.g., Task.TaskType.SEND_EMAIL)
        :param data: Dictionary containing task-specific data
        """
        if not isinstance(data, dict):
            raise ValueError(f"data must be a dict. Got type '{type(data)}' instead.")

        return Task.objects.create(
            type=task_type,
            data=data,
        )

    @staticmethod
    @transaction.atomic
    def get_next_task() -> Task | None:
        """
        Atomically select and lock the next available task in the queue.
        Uses SELECT FOR UPDATE with SKIP LOCKED to handle concurrent workers.
        Marks the task as started within the transaction to prevent race conditions.
        """
        task = (
            Task.objects.filter(started_at__isnull=True).select_for_update(skip_locked=True).first()
        )

        if task:
            task.started_at = timezone.now()
            task.save(update_fields=["started_at"])

        return task

    @staticmethod
    def get_task_stats() -> dict[str, int]:
        """Get statistics about tasks in the queue"""
        return {
            "pending": Task.objects.filter(started_at__isnull=True).count(),
            "running": Task.objects.filter(
                started_at__isnull=False, completed_at__isnull=True, failed_at__isnull=True
            ).count(),
            "completed": Task.objects.filter(completed_at__isnull=False).count(),
            "failed": Task.objects.filter(failed_at__isnull=False).count(),
            "total": Task.objects.count(),
        }

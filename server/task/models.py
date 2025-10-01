import json
import sys
from collections.abc import Callable
from typing import Any

from django.db import models
from django.utils import timezone


class Task(models.Model):
    class TaskType(models.TextChoices):
        SEND_EMAIL = "SEND_EMAIL", "Send Email"

    type = models.CharField(max_length=50, choices=TaskType.choices)
    data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)

    result = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    error = models.TextField(blank=True)
    failed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["started_at", "completed_at", "failed_at"]),
        ]

    def __str__(self) -> str:
        status = "pending"
        if self.failed_at:
            status = "failed"
        elif self.completed_at:
            status = "completed"
        elif self.started_at:
            status = "running"

        return f"Task {self.id} ({status}) - {self.get_type_display()}"

    def run_task(self) -> None:
        """Execute the task based on its type"""
        try:
            self.started_at = timezone.now()
            self.save()
            sys.stdout.write(f"Started task {self.id} - {self.type}\n")

            function = self._get_task_function()
            if not function:
                raise ValueError(f"No handler found for task type: {self.type}")

            self._execute(function)

        except Exception as e:
            self.error = str(e)
            self.failed_at = timezone.now()
            self.save()
            sys.stdout.write(f"Failed task {self.id}: {e}\n")

    def _get_task_function(self) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
        """Map task type to its corresponding function"""
        from server.task.email_tasks import send_email

        task_handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            self.TaskType.SEND_EMAIL: send_email,
        }

        return task_handlers.get(self.type, None)

    def _execute(self, function: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        """Execute the task's function and save the result or error"""
        try:
            sys.stdout.write(f"Executing {self.type} with data={self.data}\n")

            result = function(self.data)

            self.result = json.loads(json.dumps(result, default=str))
            self.completed_at = timezone.now()
            sys.stdout.write(f"Completed task {self.id}\n")

        except Exception as e:
            self.error = str(e)
            self.failed_at = timezone.now()
            sys.stdout.write(f"Failed task {self.id}: {self.error}\n")
        finally:
            self.save()

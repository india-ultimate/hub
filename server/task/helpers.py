"""
Helper functions for queuing common tasks
"""

from django.core.mail import EmailMultiAlternatives

from server.task.email_tasks import serialize_email_message
from server.task.manager import TaskManager
from server.task.models import Task


def queue_emails(messages: list[EmailMultiAlternatives]) -> list[Task]:
    """
    Queue emails for background sending using the task queue.
    Creates one task per email.

    :param messages: List of EmailMultiAlternatives objects to send
    :return: List of created Task objects
    """
    tasks = []
    for msg in messages:
        email_data = serialize_email_message(msg)
        task = TaskManager.add_task(
            task_type=Task.TaskType.SEND_EMAIL,
            data=email_data,
        )
        tasks.append(task)

    return tasks

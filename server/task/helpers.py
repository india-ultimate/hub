"""
Helper functions for queuing common tasks
"""

import re
from html import unescape

from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

from server.task.email_tasks import serialize_email_message
from server.task.manager import TaskManager
from server.task.models import Task


def html_to_text(html: str) -> str:
    """The plain-text part of an HTML email: no head, links written out."""
    html = re.sub(r"<head.*?</head>", "", html, flags=re.S)
    html = re.sub(r"<(p|div) [^>]*data-notext.*?</\1>", "", html, flags=re.S)
    html = re.sub(
        r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        lambda m: m[2] if m[2].strip() == m[1] or m[1].startswith("mailto:") else f"{m[2]}: {m[1]}",
        html,
        flags=re.S,
    )
    html = re.sub(r"\s+", " ", html)
    html = re.sub(r"<br\s*/?>", "\n", html)
    html = re.sub(r"</(p|tr|table|h\d)>", "\n\n", html)
    text = unescape(strip_tags(html.replace("</td>", " ")))
    lines = (line.strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


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

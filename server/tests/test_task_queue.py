from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import TestCase

from server.task.helpers import queue_emails
from server.task.manager import TaskManager
from server.task.models import Task


class TestTaskQueue(TestCase):
    def test_create_task(self) -> None:
        """Test creating a task"""
        task = TaskManager.add_task(
            task_type=Task.TaskType.SEND_EMAIL,
            data={"test": "data"},
        )

        self.assertIsNotNone(task.id)
        self.assertEqual(task.type, Task.TaskType.SEND_EMAIL)
        self.assertEqual(task.data, {"test": "data"})
        self.assertIsNone(task.started_at)
        self.assertIsNone(task.completed_at)
        self.assertIsNone(task.failed_at)

    def test_get_next_task(self) -> None:
        """Test fetching the next task from queue"""
        task1 = TaskManager.add_task(
            task_type=Task.TaskType.SEND_EMAIL,
            data={"email": "first"},
        )
        TaskManager.add_task(
            task_type=Task.TaskType.SEND_EMAIL,
            data={"email": "second"},
        )

        next_task = TaskManager.get_next_task()
        self.assertIsNotNone(next_task)
        if next_task:
            self.assertEqual(next_task.id, task1.id)

    def test_task_stats(self) -> None:
        """Test getting task statistics"""
        TaskManager.add_task(task_type=Task.TaskType.SEND_EMAIL, data={})
        TaskManager.add_task(task_type=Task.TaskType.SEND_EMAIL, data={})

        stats = TaskManager.get_task_stats()

        self.assertEqual(stats["pending"], 2)
        self.assertEqual(stats["running"], 0)
        self.assertEqual(stats["completed"], 0)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["total"], 2)

    def test_send_email_task(self) -> None:
        """Test sending an email through the task queue"""
        email = EmailMultiAlternatives(
            subject="Test Subject",
            body="Test Body",
            from_email="from@example.com",
            to=["to@example.com"],
        )
        email.attach_alternative("<p>Test HTML</p>", "text/html")

        tasks = queue_emails([email])

        self.assertEqual(len(tasks), 1)
        task = tasks[0]

        self.assertEqual(task.type, Task.TaskType.SEND_EMAIL)
        self.assertEqual(task.data["subject"], "Test Subject")
        self.assertEqual(task.data["body"], "Test Body")
        self.assertEqual(task.data["to"], ["to@example.com"])
        self.assertEqual(task.data["html_content"], "<p>Test HTML</p>")

    def test_run_send_email_task(self) -> None:
        """Test running a send email task"""
        mail.outbox = []

        email = EmailMultiAlternatives(
            subject="Test Subject",
            body="Test Body",
            from_email="from@example.com",
            to=["to@example.com"],
        )

        tasks = queue_emails([email])
        task = tasks[0]

        task.run_task()

        task.refresh_from_db()
        self.assertIsNotNone(task.started_at)
        self.assertIsNotNone(task.completed_at)
        self.assertIsNone(task.failed_at)
        self.assertEqual(task.error, "")

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.subject, "Test Subject")
        self.assertEqual(sent_email.to, ["to@example.com"])

    def test_queue_multiple_emails(self) -> None:
        """Test queuing multiple emails creates multiple tasks"""
        mail.outbox = []

        emails = [
            EmailMultiAlternatives(
                subject=f"Email {i}",
                body=f"Body {i}",
                from_email="from@example.com",
                to=[f"user{i}@example.com"],
            )
            for i in range(3)
        ]

        tasks = queue_emails(emails)

        self.assertEqual(len(tasks), 3)

        for task in tasks:
            task.run_task()
            task.refresh_from_db()
            self.assertIsNotNone(task.completed_at)
            self.assertIsNone(task.failed_at)

        self.assertEqual(len(mail.outbox), 3)
        for idx, sent_email in enumerate(mail.outbox):
            self.assertEqual(sent_email.subject, f"Email {idx}")
            self.assertEqual(sent_email.to, [f"user{idx}@example.com"])

    def test_task_with_invalid_type(self) -> None:
        """Test that task fails gracefully with invalid task type"""
        task = Task.objects.create(
            type="INVALID_TYPE",
            data={},
        )

        task.run_task()

        task.refresh_from_db()
        self.assertIsNotNone(task.failed_at)
        self.assertIsNotNone(task.error)
        self.assertIn("No handler found", task.error)

    def test_task_string_representation(self) -> None:
        """Test task string representation"""
        task = TaskManager.add_task(
            task_type=Task.TaskType.SEND_EMAIL,
            data={"test": "data"},
        )

        task_str = str(task)
        self.assertIn(f"Task {task.id}", task_str)
        self.assertIn("pending", task_str)
        self.assertIn("Send Email", task_str)

        task.started_at = task.created_at
        task.save()
        task_str = str(task)
        self.assertIn("running", task_str)

        task.completed_at = task.created_at
        task.save()
        task_str = str(task)
        self.assertIn("completed", task_str)

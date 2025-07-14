import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from django.core import mail
from django.core.mail import EmailMultiAlternatives


class EmailWorker:
    """Background email worker for sending emails asynchronously"""

    def __init__(self, batch_size: int = 50, batch_delay: float = 0.1) -> None:
        self.email_queue: queue.Queue[
            tuple[list[EmailMultiAlternatives], str, Callable[[int, int, str], None] | None] | None
        ] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.worker_running = False
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self.stats: dict[str, Any] = {
            "total_emails_sent": 0,
            "total_batches_processed": 0,
            "failed_batches": 0,
            "last_error": None,
        }

    def start(self) -> None:
        """Start the email worker thread"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            print("Email worker started")

    def stop(self) -> None:
        """Stop the email worker thread gracefully"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_running = False
            self.email_queue.put(None)  # Send shutdown signal
            self.worker_thread.join(timeout=5)  # Wait up to 5 seconds
            print("Email worker stopped")

    def _worker(self) -> None:
        """Background worker thread for sending emails"""
        while self.worker_running:
            try:
                # Get email task from queue with timeout
                email_task = self.email_queue.get(timeout=1)
                if email_task is None:  # Shutdown signal
                    break

                messages, task_id, callback = email_task

                try:
                    # Process emails in batches
                    total_sent = 0
                    total_batches = (len(messages) + self.batch_size - 1) // self.batch_size

                    for i in range(0, len(messages), self.batch_size):
                        batch = messages[i : i + self.batch_size]
                        batch_number = i // self.batch_size + 1

                        try:
                            # Send batch using Django's connection
                            connection = mail.get_connection()
                            emails_sent = connection.send_messages(batch)
                            total_sent += emails_sent
                            if self.stats["total_emails_sent"] is not None:
                                self.stats["total_emails_sent"] += emails_sent
                            self.stats["total_batches_processed"] += 1

                            print(
                                f"Sent batch {batch_number}/{total_batches} ({emails_sent} emails) for task {task_id}"
                            )

                            # Small delay between batches
                            time.sleep(self.batch_delay)

                        except Exception as e:
                            print(
                                f"Failed to send batch {batch_number}/{total_batches} for task {task_id}: {e}"
                            )
                            self.stats["failed_batches"] += 1
                            self.stats["last_error"] = str(e)
                            continue

                    print(f"Successfully sent {total_sent} emails for task {task_id}")

                    # Call callback if provided
                    if callback:
                        try:
                            callback(total_sent, len(messages), task_id)
                        except Exception as e:
                            print(f"Error in email callback for task {task_id}: {e}")

                    # Mark task as done only after successful processing
                    self.email_queue.task_done()

                except Exception as e:
                    print(f"Failed to process emails for task {task_id}: {e}")
                    self.stats["last_error"] = str(e)
                    # Mark task as done even if processing failed
                    self.email_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Email worker error: {e}")
                self.stats["last_error"] = str(e)
                continue

    def queue_emails(
        self,
        messages: list[EmailMultiAlternatives],
        task_id: str,
        callback: Callable[[int, int, str], None] | None = None,
    ) -> bool:
        """Queue emails for background sending"""
        if not self.worker_running:
            self.start()

        try:
            self.email_queue.put((messages, task_id, callback))
            print(f"Queued {len(messages)} emails for task {task_id} for background sending")
            return True
        except Exception as e:
            print(f"Failed to queue emails for task {task_id}: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Get the current status of the email worker"""
        return {
            "worker_running": self.worker_running
            and self.worker_thread
            and self.worker_thread.is_alive(),
            "queue_size": self.email_queue.qsize(),
            "worker_thread_alive": self.worker_thread.is_alive() if self.worker_thread else False,
            "stats": self.stats.copy(),
        }

    def get_queue_size(self) -> int:
        """Get the current queue size"""
        return self.email_queue.qsize()


# Global email worker instance
email_worker = EmailWorker()


def get_email_worker() -> EmailWorker:
    """Get the global email worker instance"""
    return email_worker


def queue_emails(
    messages: list[EmailMultiAlternatives],
    task_id: str,
    callback: Callable[[int, int, str], None] | None = None,
) -> bool:
    """Queue emails for background sending using the global worker"""
    return email_worker.queue_emails(messages, task_id, callback)


def get_email_worker_status() -> dict[str, Any]:
    """Get the status of the global email worker"""
    return email_worker.get_status()


def stop_email_worker() -> None:
    """Stop the global email worker"""
    email_worker.stop()

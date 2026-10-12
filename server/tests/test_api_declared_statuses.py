"""Every status an endpoint returns must be in its `response=`: ninja raises
ConfigError for one that isn't, and the caller gets a 500 instead of the message."""

from datetime import timedelta
from typing import Any
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from server.core.models import User
from server.election.models import Election, EligibleVoter
from server.tests.base import ApiBaseTestCase


class TestElectionStatuses(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.election = Election.objects.create(
            title="Test Election",
            description="Test Description",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            voting_method="IRV",
        )

    def as_staff(self) -> None:
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def assert_message(self, response: Any, status: int, text: str) -> None:
        self.assertEqual(status, response.status_code, response.content)
        self.assertIn(text, response.json()["message"])

    def test_a_non_staff_user_cannot_create_an_election(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/election/",
            {
                "title": "T",
                "description": "D",
                "start_date": "2030-01-01T00:00:00Z",
                "end_date": "2030-01-08T00:00:00Z",
            },
            content_type="application/json",
        )
        self.assert_message(response, 403, "Only staff")

    def test_a_non_staff_user_cannot_add_a_candidate(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/election/{self.election.id}/candidates/",
            {"user_id": self.user.id, "bio": "Hi"},
            content_type="application/json",
        )
        self.assert_message(response, 403, "Only staff")

    def test_a_non_staff_user_cannot_import_voters(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/election/{self.election.id}/eligible-voters/",
            {"file": SimpleUploadedFile("v.csv", b"email\n")},
        )
        self.assert_message(response, 403, "Only staff")

    def test_notifying_an_election_with_no_voters_says_so(self) -> None:
        self.as_staff()
        response = self.client.post(f"/api/election/{self.election.id}/send-notification/")
        self.assert_message(response, 400, "No eligible voters")

    def test_a_queue_failure_while_notifying_says_so(self) -> None:
        voter = User.objects.create_user(username="v@example.com", email="v@example.com")
        EligibleVoter.objects.create(election=self.election, user=voter)
        self.as_staff()
        with mock.patch("server.election.api.queue_emails", side_effect=RuntimeError("down")):
            response = self.client.post(f"/api/election/{self.election.id}/send-notification/")
        self.assert_message(response, 500, "Failed to queue emails")


class TestUpdateScheduleStatuses(ApiBaseTestCase):
    def test_a_non_manager_is_refused_with_the_message(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/tournament/{self.tournament.id}/update-schedule",
            {"schedule_file": SimpleUploadedFile("s.csv", b"a,b\n")},
        )
        self.assertEqual(401, response.status_code, response.content)
        self.assertIn("Only staff", response.json()["message"])

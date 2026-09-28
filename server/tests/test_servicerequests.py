from django.core import mail
from django.test import TestCase

from server.core.models import Player, User
from server.season.models import Season
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType
from server.subscription.models import SponsorshipGrant
from server.subscription.sponsorship import has_grant


class ServiceRequestSignalTest(TestCase):
    def setUp(self) -> None:
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            phone="1234567890",
            password="testpass123",  # noqa: S106
        )
        self.player = Player.objects.create(
            user=self.user,
            date_of_birth="1990-01-01",
            gender="M",
            match_up="M",
            city="Test City",
        )
        self.season = Season.objects.get(name="Season 2025-2026")

    def test_sponsored_subscription_approval_signal(self) -> None:
        """Approving a request grants its season"""
        # Create a sponsored subscription request
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="Please approve my sponsored subscription",
            season=self.season,
            status=ServiceRequestStatus.PENDING,
        )

        # Add the player to the service request
        service_request.service_players.add(self.player)

        # Verify player is not sponsored initially
        self.assertFalse(has_grant(self.player, self.season))

        # Approve the service request
        service_request.status = ServiceRequestStatus.APPROVED
        service_request.save()

        self.assertTrue(has_grant(self.player, self.season))

    def test_non_sponsored_request_does_not_affect_player(self) -> None:
        """Test that approving a non-sponsored request grants nothing"""
        # Create a different type of service request (if we had other types)
        # For now, we'll test with a sponsored request but reject it
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="Please approve my sponsored subscription",
            season=self.season,
            status=ServiceRequestStatus.PENDING,
        )

        # Add the player to the service request
        service_request.service_players.add(self.player)

        # Verify player is not sponsored initially
        self.assertFalse(has_grant(self.player, self.season))

        # Reject the service request instead of approving
        service_request.status = ServiceRequestStatus.REJECTED
        service_request.save()

        # Verify player is still not sponsored
        self.assertFalse(has_grant(self.player, self.season))

    def test_signal_only_triggers_on_approval(self) -> None:
        """Test that the signal only triggers when status changes to APPROVED"""
        # Create and approve a request
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="Please approve my sponsored subscription",
            season=self.season,
            status=ServiceRequestStatus.APPROVED,  # Create directly as approved
        )

        # Add the player to the service request
        service_request.service_players.add(self.player)

        # Verify player is still not sponsored (signal only triggers on status change)
        self.assertFalse(has_grant(self.player, self.season))

        # Now change from approved to rejected and back to approved
        service_request.status = ServiceRequestStatus.REJECTED
        service_request.save()

        self.assertFalse(has_grant(self.player, self.season))

        # Change back to approved - this should trigger the signal
        service_request.status = ServiceRequestStatus.APPROVED
        service_request.save()

        self.assertTrue(has_grant(self.player, self.season))

    def test_email_sent_on_approval(self) -> None:
        """Test that an email is sent when a service request is approved"""
        # Clear the outbox
        mail.outbox = []

        # Create a service request
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="Please approve my sponsored subscription",
            season=self.season,
            status=ServiceRequestStatus.PENDING,
        )

        # Add the player to the service request
        service_request.service_players.add(self.player)

        # Approve the service request
        service_request.status = ServiceRequestStatus.APPROVED
        service_request.save()

        # Check that an email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Check email details
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.user.email])
        self.assertIn("Service Request Approved", email.subject)
        self.assertIn("🎉 Great news! Your service request has been approved", email.body)
        self.assertIn("text/html", email.alternatives[0][1])  # type: ignore[attr-defined]

    def test_email_sent_on_rejection(self) -> None:
        """Test that an email is sent when a service request is rejected"""
        # Clear the outbox
        mail.outbox = []

        # Create a service request
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="Please approve my sponsored subscription",
            season=self.season,
            status=ServiceRequestStatus.PENDING,
        )

        # Add the player to the service request
        service_request.service_players.add(self.player)

        # Reject the service request
        service_request.status = ServiceRequestStatus.REJECTED
        service_request.save()

        # Check that an email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Check email details
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.user.email])
        self.assertIn("Service Request Update", email.subject)
        self.assertIn(
            "📋 We have reviewed your service request and unfortunately, it has not been approved at this time",
            email.body,
        )
        self.assertIn("text/html", email.alternatives[0][1])  # type: ignore[attr-defined]

    def test_no_email_sent_on_creation(self) -> None:
        """Test that no email is sent when a service request is created"""
        # Clear the outbox
        mail.outbox = []

        # Create a service request (this should not send an email)
        ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="Please approve my sponsored subscription",
            season=self.season,
            status=ServiceRequestStatus.PENDING,
        )

        # Check that no email was sent
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_sent_on_pending_status(self) -> None:
        """Test that no email is sent when status changes to PENDING"""
        # Clear the outbox
        mail.outbox = []

        # Create a service request
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="Please approve my sponsored subscription",
            season=self.season,
            status=ServiceRequestStatus.APPROVED,
        )

        # Change status to PENDING (this should not send an email)
        service_request.status = ServiceRequestStatus.PENDING
        service_request.save()

        # Check that no email was sent
        self.assertEqual(len(mail.outbox), 0)

    def test_resaving_an_approved_request_leaves_a_revoked_grant_revoked(self) -> None:
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="Please approve my sponsored subscription",
            season=self.season,
        )
        service_request.service_players.add(self.player)
        service_request.status = ServiceRequestStatus.APPROVED
        service_request.save()
        self.assertEqual(len(mail.outbox), 1)

        SponsorshipGrant.objects.filter(player=self.player).delete()
        service_request.message = "Edited by staff"
        service_request.save()

        self.assertFalse(has_grant(self.player, self.season))
        self.assertEqual(len(mail.outbox), 1)

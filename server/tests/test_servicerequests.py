from django.test import TestCase

from server.core.models import Player, User
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType


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
            sponsored=False,  # Initially not sponsored
        )

    def test_sponsored_membership_approval_signal(self) -> None:
        """Test that approving a sponsored membership request sets player.sponsored=True"""
        # Create a sponsored membership request
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_MEMBERSHIP,
            message="Please approve my sponsored membership",
            status=ServiceRequestStatus.PENDING,
        )

        # Add the player to the service request
        service_request.service_players.add(self.player)

        # Verify player is not sponsored initially
        self.player.refresh_from_db()
        self.assertFalse(self.player.sponsored)

        # Approve the service request
        service_request.status = ServiceRequestStatus.APPROVED
        service_request.save()

        # Verify player is now sponsored
        self.player.refresh_from_db()
        self.assertTrue(self.player.sponsored)

    def test_non_sponsored_request_does_not_affect_player(self) -> None:
        """Test that approving a non-sponsored request doesn't affect player.sponsored"""
        # Create a different type of service request (if we had other types)
        # For now, we'll test with a sponsored request but reject it
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_MEMBERSHIP,
            message="Please approve my sponsored membership",
            status=ServiceRequestStatus.PENDING,
        )

        # Add the player to the service request
        service_request.service_players.add(self.player)

        # Verify player is not sponsored initially
        self.player.refresh_from_db()
        self.assertFalse(self.player.sponsored)

        # Reject the service request instead of approving
        service_request.status = ServiceRequestStatus.REJECTED
        service_request.save()

        # Verify player is still not sponsored
        self.player.refresh_from_db()
        self.assertFalse(self.player.sponsored)

    def test_signal_only_triggers_on_approval(self) -> None:
        """Test that the signal only triggers when status changes to APPROVED"""
        # Create and approve a request
        service_request = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_SPONSORED_MEMBERSHIP,
            message="Please approve my sponsored membership",
            status=ServiceRequestStatus.APPROVED,  # Create directly as approved
        )

        # Add the player to the service request
        service_request.service_players.add(self.player)

        # Verify player is still not sponsored (signal only triggers on status change)
        self.player.refresh_from_db()
        self.assertFalse(self.player.sponsored)

        # Now change from approved to rejected and back to approved
        service_request.status = ServiceRequestStatus.REJECTED
        service_request.save()

        self.player.refresh_from_db()
        self.assertFalse(self.player.sponsored)

        # Change back to approved - this should trigger the signal
        service_request.status = ServiceRequestStatus.APPROVED
        service_request.save()

        # Verify player is now sponsored
        self.player.refresh_from_db()
        self.assertTrue(self.player.sponsored)

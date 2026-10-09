"""A college ID whose images were removed reads as expired, not as done."""

import datetime

import pytest

from server.core.models import CollegeId, Player
from server.tests.localserver import APP_URL
from server.tests.test_registration_integration import RegistrationPageCase
from server.utils import today


@pytest.mark.django_db(transaction=True)
class TestCollegeIdPageIntegration(RegistrationPageCase):
    def student(self) -> Player:
        p = self.player("Ravi", "Student", entry=False)
        p.occupation = "College-Student"
        p.save()
        return p

    def test_an_inactive_card_says_its_images_were_removed(self) -> None:
        p = self.student()
        CollegeId.objects.create(
            player=p,
            expiry=today() - datetime.timedelta(days=60),
            card_front="",
            card_back="",
            images_removed_at=today() - datetime.timedelta(days=29),
        )
        self.sign_in_as(p.user)
        self.open(f"{APP_URL}/college-id/{p.id}")
        self.assert_text("images removed")
        self.assert_element_absent('a:contains("View Front")')

    def test_an_expired_card_with_images_says_expired(self) -> None:
        p = self.student()
        CollegeId.objects.create(
            player=p,
            expiry=today() - datetime.timedelta(days=5),
            card_front="college_ids/f.jpg",
            card_back="college_ids/b.jpg",
        )
        self.sign_in_as(p.user)
        self.open(f"{APP_URL}/college-id/{p.id}")
        self.assert_text("Expired")

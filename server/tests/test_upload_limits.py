"""Files over the server's limits are refused in the browser, before uploading."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from server.core.models import Player, Team
from server.tests.localserver import APP_URL
from server.tests.test_registration_integration import RegistrationPageCase
from server.ticket.models import Ticket


@pytest.mark.django_db(transaction=True)
class TestUploadLimitsIntegration(RegistrationPageCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        folder = Path(tempfile.mkdtemp())
        # Over the 10 MB a file Cloudinary takes.
        cls.big_file = folder / "scan.jpg"
        cls.big_file.write_bytes(b"\0" * (11 * 1024 * 1024))
        # Small files, huge photos: past what the server shrinks (50 MP), and
        # past what Cloudinary takes as it is (25 MP).
        cls.photo_60mp = folder / "huge.jpg"
        Image.new("L", (8000, 7500)).save(cls.photo_60mp, quality=10)
        cls.photo_30mp = folder / "large.png"
        Image.new("L", (6000, 5000)).save(cls.photo_30mp, optimize=True)
        cls.photo = folder / "card.png"
        Image.new("RGB", (1200, 800)).save(cls.photo)

    def student(self) -> Player:
        p = self.player("Ravi", "Student", entry=False)
        p.occupation = "College-Student"
        p.save()
        return p

    def attach(self, selector: str, path: Path) -> None:
        # The file inputs are transparent, laid over their drop zone.
        self.wait_for_element_present(selector)
        self.driver.find_element("css selector", selector).send_keys(str(path))

    def open_college_id_form(self, p: Player) -> None:
        self.sign_in_as(p.user)
        self.open(f"{APP_URL}/college-id/{p.id}")
        self.wait_for_element_present("input#card_front")

    def test_a_card_over_10_mb_is_refused(self) -> None:
        p = self.student()
        self.open_college_id_form(p)
        self.attach("input#card_front", self.big_file)
        self.click('button[type="submit"]')
        self.assert_text("Files must be 10 MB or smaller")

    def test_a_card_photo_over_50_megapixels_is_refused(self) -> None:
        p = self.student()
        self.open_college_id_form(p)
        self.attach("input#card_front", self.photo_60mp)
        self.click('button[type="submit"]')
        self.assert_text("under 50 megapixels")

    def test_a_png_over_28_megapixels_is_refused(self) -> None:
        # A PNG may be transparent, which the server shrinks only to ~28 MP.
        p = self.student()
        self.open_college_id_form(p)
        self.attach("input#card_front", self.photo_30mp)
        self.click('button[type="submit"]')
        self.assert_text("under 28 megapixels")

    def test_an_ordinary_photo_is_let_through(self) -> None:
        p = self.student()
        self.open_college_id_form(p)
        self.attach("input#card_front", self.photo)
        self.click('button[type="submit"]')
        self.assert_text("Please upload your College ID Card's Back Side.")
        self.assert_text_not_visible("10 MB or smaller")
        self.assert_text_not_visible("megapixels")

    def test_a_ticket_attachment_over_25_megapixels_is_refused(self) -> None:
        # Attachments go to Cloudinary as they are, without the server's shrink.
        p = self.student()
        ticket = Ticket.objects.create(title="My name", description="-", created_by=p.user)
        self.sign_in_as(p.user)
        self.open(f"{APP_URL}/tickets/{ticket.id}")
        self.assert_text("up to 10 MB")
        self.attach("input#attachment", self.photo_30mp)
        self.assert_text("under 25 megapixels")
        self.assert_text_not_visible("Selected: large.png")

    def test_a_profile_picture_over_25_megapixels_is_refused(self) -> None:
        # Profile pictures also go to Cloudinary as they are.
        p = self.student()
        self.sign_in_as(p.user)
        self.open(f"{APP_URL}/dashboard")
        self.attach('input[type="file"][accept="image/*"]', self.photo_30mp)
        self.assert_text("under 25 megapixels")

    def test_a_profile_picture_over_10_mb_is_refused(self) -> None:
        p = self.student()
        self.sign_in_as(p.user)
        self.open(f"{APP_URL}/dashboard")
        big_photo = self.big_file.with_name("big.png")
        big_photo.write_bytes(self.big_file.read_bytes())
        self.attach('input[type="file"][accept="image/*"]', big_photo)
        self.assert_text("10 MB or smaller")

    def test_a_team_with_a_logo_can_still_be_edited(self) -> None:
        # The form loads the logo as its URL, not a File: there's nothing to check.
        p = self.student()
        team = Team.objects.create(
            name="Logo Team",
            category="Club",
            state_ut="KA",
            city="Mysuru",
            image="team_logos/l.png",
        )
        team.admins.add(p.user)
        self.sign_in_as(p.user)
        self.open(f"{APP_URL}/team/{team.slug}/edit")
        self.wait_for_element_present("input#city")
        self.update_text("input#city", "Bengaluru")
        self.click('button[type="submit"]')
        for _ in range(20):
            team.refresh_from_db()
            if team.city == "Bengaluru":
                break
            self.sleep(0.5)
        self.assertEqual("Bengaluru", team.city)

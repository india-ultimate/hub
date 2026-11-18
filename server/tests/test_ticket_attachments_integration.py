"""Opening a ticket reply's attachments full screen."""

from contextlib import ExitStack

import pytest
from selenium.webdriver.common.keys import Keys
from seleniumbase import BaseCase

from server.core.models import User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server
from server.ticket.models import Ticket, TicketMessage

CLOUD = "https://res.cloudinary.com/demo"
POINTER = """
const real = window.matchMedia.bind(window);
window.matchMedia = q =>
  q === "(pointer: fine)"
    ? { matches: %s, media: q, addEventListener() {}, removeEventListener() {} }
    : real(q);
"""
STAGE = "#attachment-dialog-{pk} .overscroll-contain"


@pytest.mark.django_db(transaction=True)
class TestTicketAttachmentsIntegration(BaseCase):
    sign_in_as = test_ui.TestIntegration.sign_in_as

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def open_ticket_with(self, attachment: str) -> int:
        player = User.objects.create_user("player@example.com", "player@example.com", "pw")
        ticket = Ticket.objects.create(title="Proof", description="-", created_by=player)
        message = TicketMessage.objects.create(
            ticket=ticket, sender=player, message="See file", attachment=attachment
        )
        self.sign_in_as(player)
        self.open(f"{APP_URL}/tickets/{ticket.pk}")
        return message.pk

    def is_open(self, pk: int) -> bool:
        return self.execute_script(f"return document.querySelector('#attachment-dialog-{pk}').open")

    def active_id(self) -> str:
        return self.execute_script("return document.activeElement.id")

    def open_image(self) -> tuple[int, str]:
        url = f"{CLOUD}/image/upload/sample.jpg"
        pk = self.open_ticket_with(url)
        self.assert_element_absent("body.overflow-hidden")
        self.click(f"#attachment-open-{pk}")
        self.assert_element(f'#attachment-dialog-{pk} img[src="{url}"]')
        return pk, url

    # Breaks if: an image reply stops opening full screen, focus does not go to
    # Close, Esc stops closing it, or focus is lost instead of returning.
    def test_image_opens_full_screen_and_esc_closes(self) -> None:
        pk, _ = self.open_image()
        self.assertTrue(self.is_open(pk))
        self.assertEqual(self.active_id(), f"attachment-close-{pk}")
        self.assert_element("body.overflow-hidden")
        self.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
        self.assertFalse(self.is_open(pk))
        self.assert_element_absent("body.overflow-hidden")
        self.assertEqual(self.active_id(), f"attachment-open-{pk}")

    # Breaks if: the Close button stops closing or returning focus.
    def test_close_button_closes_and_returns_focus(self) -> None:
        pk, _ = self.open_image()
        self.click(f"#attachment-close-{pk}")
        self.assertFalse(self.is_open(pk))
        self.assertEqual(self.active_id(), f"attachment-open-{pk}")

    # Breaks if: a click beside the image stops closing, or a press that began
    # on the image and ended outside it closes.
    def test_clicking_beside_the_image_closes_it(self) -> None:
        pk, _ = self.open_image()
        stage = STAGE.format(pk=pk)
        press = f"""
            const stage = document.querySelector('{stage}');
            const down = arguments[0] === 'stage' ? stage : stage.querySelector('img');
            down.dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true}}));
            stage.click();
        """
        self.execute_script(press, "image")
        self.assertTrue(self.is_open(pk))
        self.execute_script(press, "stage")
        self.assertFalse(self.is_open(pk))
        self.assertEqual(self.active_id(), f"attachment-open-{pk}")

    # Breaks if: an image that fails to load leaves a blank dialog.
    def test_a_broken_image_says_so(self) -> None:
        pk = self.open_ticket_with("https://files.invalid/image/upload/missing.jpg")
        self.click(f"#attachment-open-{pk}")
        self.assert_element('[role="alert"]:contains("Couldn\'t load this image.")')
        self.assert_element(f'#attachment-dialog-{pk} a[aria-label="Open in new tab"]')

    # Breaks if: a PDF stops previewing in the page on a mouse-and-keyboard device.
    def test_pdf_previews_in_the_page_on_desktop(self) -> None:
        pk = self.open_ticket_with(f"{CLOUD}/image/upload/v1/stream_x.pdf")
        self.execute_script(POINTER % "true")
        self.click(f"#attachment-open-{pk}")
        self.assert_element(f'#attachment-dialog-{pk}[open] iframe[src$="stream_x.pdf"]')

    # Breaks if: a touch device gets the iframe instead of a new tab.
    def test_pdf_opens_a_new_tab_on_touch_devices(self) -> None:
        url = f"{CLOUD}/image/upload/v1/stream_x.pdf"
        pk = self.open_ticket_with(url)
        self.execute_script(POINTER % "false")
        self.execute_script("window.opened = []; window.open = (...a) => window.opened.push(a);")
        self.click(f"#attachment-open-{pk}")
        self.assertEqual(self.execute_script("return window.opened"), [[url, "_blank", "noopener"]])
        self.assertFalse(self.is_open(pk))

    # Breaks if: a file we cannot preview gains a preview button.
    def test_other_files_only_download(self) -> None:
        pk = self.open_ticket_with(f"{CLOUD}/raw/upload/notes.docx")
        self.assert_element('button:contains("Download notes.docx")')
        self.assert_element_absent(f"#attachment-open-{pk}")

    # Breaks if: a non-https attachment gains a preview.
    def test_http_images_only_download(self) -> None:
        pk = self.open_ticket_with("http://files.example.com/photo.jpg")
        self.assert_element('button:contains("Download photo.jpg")')
        self.assert_element_absent(f"#attachment-open-{pk}")

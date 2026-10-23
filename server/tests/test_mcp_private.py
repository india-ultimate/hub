import time

from django.test import SimpleTestCase

from server.mcp.private import scrub


class TestScrub(SimpleTestCase):
    def test_contact_fields_go_wherever_they_are(self) -> None:
        self.assertEqual(
            {"full_name": "Mira Das", "player_id": 7, "guardian": {"full_name": "Ana"}},
            scrub(
                {
                    "full_name": "Mira Das",
                    "player_id": 7,
                    "email": "mira@example.com",
                    "phone": 9812345678,
                    "date_of_birth": "2010-04-01",
                    "guardian": {
                        "full_name": "Ana",
                        "guardian_email": "a@b.co",
                        "Phone": None,
                        "phoneNumber": "x",
                        "dateOfBirth": "x",
                        "born": "x",
                        "birthday": "x",
                        "tel": "x",
                    },
                }
            ),
        )

    def test_fields_that_only_mention_contact_stay(self) -> None:
        kept = {
            "emails_sent": 3,
            "email_verified": True,
            "phone": False,
            "email_template": "welcome",
            "whatsapp_group": "https://chat.whatsapp.com/abc",
            "would_email_invite": True,
        }
        self.assertEqual(kept, scrub(kept))

    def test_emails_phones_and_birth_dates_in_text_are_hidden(self) -> None:
        texts = {
            "Write to mira.das+hub@example.co.in or call +91 98123 45678.": (
                "Write to [email hidden] or call [phone hidden]."
            ),
            "Mobile 9812345678 or 98 1234-5678, abroad +44 20 7946 0958": (
                "Mobile [phone hidden] or [phone hidden], abroad [phone hidden]"
            ),
            "919812345678, 91-98123-45678, (+91) 98123 45678, 98123.45678": (
                "[phone hidden], [phone hidden], [phone hidden], [phone hidden]"
            ),
            "Office 022 2345 6789": "Office [phone hidden]",
            "mailto:mira@example.com": "mailto:[email hidden]",
            "See https://x.org/find?who=mira@example.com": "See [email hidden]",
            "DOB: 2010-04-01, born on 12 March 2010, Birthday 01/04/2010": (
                "[date of birth hidden], [date of birth hidden], [date of birth hidden]"
            ),
        }
        for text, hidden in texts.items():
            with self.subTest(text=text):
                self.assertEqual(hidden, scrub(text))

    def test_dates_ids_money_and_links_stay(self) -> None:
        kept = [
            "2026-10-22T21:59:22.264Z",
            "Won 13-9 on 2026-10-22, the final is 25 October 2026",
            "₹1,234",
            "order_9812345678abc",
            "pay_N8x9812345678",
            "https://hub.indiaultimate.org/upload/9812345678:abc-9812345678",
            "IU-77",
            "@everyone see the team page",
            "Write to operations@indiaultimate.org",
        ]
        self.assertEqual(kept, scrub(kept))

    def test_long_text_is_quick(self) -> None:
        started = time.monotonic()
        for text in ("9" * 100_000, "9-" * 50_000, "a" * 100_000 + "@x.org"):
            scrub(text)
        self.assertLess(time.monotonic() - started, 2)

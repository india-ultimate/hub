import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from server.receipts.money import financial_year, format_inr, in_words, india_date

UTC = datetime.timezone.utc


class TestFinancialYear(SimpleTestCase):
    def test_april_to_march(self) -> None:
        self.assertEqual(financial_year(datetime.date(2026, 4, 1)), "2026-27")
        self.assertEqual(financial_year(datetime.date(2027, 3, 31)), "2026-27")
        self.assertEqual(financial_year(datetime.date(2026, 3, 31)), "2025-26")
        self.assertEqual(financial_year(datetime.date(2099, 12, 1)), "2099-00")

    def test_the_year_turns_at_midnight_india_time(self) -> None:
        # 00:30 IST on 1 April is still 31 March in UTC.
        moment = datetime.datetime(2026, 3, 31, 19, 0, tzinfo=UTC)
        self.assertEqual(india_date(moment), datetime.date(2026, 4, 1))
        self.assertEqual(financial_year(india_date(moment)), "2026-27")
        ist = datetime.datetime(2026, 4, 1, 0, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
        self.assertEqual(india_date(ist), datetime.date(2026, 4, 1))


class TestFormatInr(SimpleTestCase):
    def test_indian_grouping_and_paise(self) -> None:
        self.assertEqual(format_inr(0), "0.00")
        self.assertEqual(format_inr(75000), "750.00")
        self.assertEqual(format_inr(150000), "1,500.00")
        self.assertEqual(format_inr(10000000), "1,00,000.00")
        self.assertEqual(format_inr(1234567899), "1,23,45,678.99")


class TestInWords(SimpleTestCase):
    def test_rupees(self) -> None:
        self.assertEqual(in_words(150000), "Rupees One Thousand Five Hundred Only")
        self.assertEqual(in_words(75000), "Rupees Seven Hundred Fifty Only")
        self.assertEqual(in_words(10000000), "Rupees One Lakh Only")
        self.assertEqual(
            in_words(12345600),
            "Rupees One Lakh Twenty-Three Thousand Four Hundred Fifty-Six Only",
        )

    def test_paise(self) -> None:
        self.assertEqual(in_words(150050), "Rupees One Thousand Five Hundred and Fifty Paise Only")

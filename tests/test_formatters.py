import unittest
from datetime import UTC, datetime

from app.services.formatters import eastern_datetime


class EasternDatetimeTests(unittest.TestCase):
    def test_converts_utc_to_eastern_standard_time(self):
        value = datetime(2026, 1, 23, 19, 15, tzinfo=UTC)

        self.assertEqual(eastern_datetime(value), "2026-01-23 02:15:00 PM EST")

    def test_converts_utc_to_eastern_daylight_time(self):
        value = datetime(2026, 7, 23, 18, 15, tzinfo=UTC)

        self.assertEqual(eastern_datetime(value), "2026-07-23 02:15:00 PM EDT")

    def test_treats_naive_values_as_utc(self):
        value = datetime(2026, 7, 23, 18, 15)

        self.assertEqual(eastern_datetime(value), "2026-07-23 02:15:00 PM EDT")

"""Synthetic tests for Fluvius local datetime conversion."""

import unittest
from datetime import datetime, timedelta

from .helpers import load_module

models = load_module("custom_components.ecoflow_p1.models")


class DsmrDatetimeTests(unittest.TestCase):
    """Preserve the meter's explicit summer/winter offset."""

    def test_valid_datetimes(self) -> None:
        for raw, expected in (
            ("260902200000S", "2026-09-02T20:00:00+02:00"),
            ("260102200000W", "2026-01-02T20:00:00+01:00"),
            ("240229120000W", "2024-02-29T12:00:00+01:00"),
            ("000101000000W", "2000-01-01T00:00:00+01:00"),
            ("991231235959W", "2099-12-31T23:59:59+01:00"),
        ):
            with self.subTest(raw=raw):
                result = models.parse_dsmr_datetime(raw)
                self.assertIsInstance(result, datetime)
                self.assertEqual(result.isoformat(), expected)

    def test_autumn_repeated_hour_is_unambiguous(self) -> None:
        summer = models.parse_dsmr_datetime("251026023000S")
        winter = models.parse_dsmr_datetime("251026023000W")
        self.assertEqual(winter - summer, timedelta(hours=1))

    def test_invalid_placeholders(self) -> None:
        for raw in (
            "",
            "000000000000W",
            "991332256199S",
            "not-a-timestamp",
            "250229120000W",
            "260902240000S",
            "260902206000S",
            "260902200060S",
            "260902200000",
            "260902200000X",
            "260902200000s",
            "26090220000S",
            "2609022000000S",
            " 260902200000S",
            "２６０９０２２０００００S",
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(models.parse_dsmr_datetime(raw))

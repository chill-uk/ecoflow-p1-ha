"""Tests for DSMR parsing."""

import unittest
from decimal import Decimal

from .helpers import load_module

load_module("custom_components.ecoflow_p1.models")
parser = load_module("custom_components.ecoflow_p1.parser")


TELEGRAM = """/ISK5\\2M550E-1011\r
\r
1-3:0.2.8(50)\r
0-0:96.1.1(45303030313233343536)\r
1-0:1.8.1(014591.819*kWh)\r
1-0:1.7.0(00.123*kW)\r
0-5:24.1.0(003)\r
0-5:96.1.0(47313233343536)\r
0-5:24.2.1(260908212458S)(11118.375*m3)\r
!6A72\r
"""


class ParserTests(unittest.TestCase):
    """Verify tolerant, identifier-based parsing."""

    def test_metadata_hex_and_unbounded_mbus_discovery(self) -> None:
        """Extract metadata and discover a channel beyond the former limit."""
        parsed = parser.parse_telegram(TELEGRAM)

        self.assertEqual(parsed.meter_info.manufacturer, "ISK")
        self.assertEqual(parsed.meter_info.model, "2M550E-1011")
        self.assertEqual(parsed.meter_info.dsmr_version, "5.0")
        self.assertEqual(parsed.meter_info.protocol_family, "DSMR")
        self.assertEqual(parsed.meter_info.electricity_serial, "E000123456")
        channel = parsed.meter_info.mbus_channels[5]
        self.assertEqual(channel.device_type, 3)
        self.assertEqual(channel.meter_serial, "G123456")
        self.assertEqual(channel.delivered, Decimal("11118.375"))
        self.assertEqual(channel.unit, "m3")

    def test_values_are_found_by_obis_and_units_are_validated(self) -> None:
        """Read values independently of line positions and reject wrong units."""
        parsed = parser.parse_telegram(TELEGRAM)
        self.assertEqual(parsed.decimal("1-0:1.7.0", "kW"), Decimal("0.123"))
        self.assertIsNone(parsed.decimal("1-0:1.7.0", "W"))
        self.assertIsNone(parsed.decimal("1-0:2.7.0", "kW"))

    def test_malformed_optional_value_does_not_break_telegram(self) -> None:
        """Ignore a malformed optional M-Bus reading."""
        telegram = TELEGRAM.replace("11118.375*m3", "not-a-number*m3")
        parsed = parser.parse_telegram(telegram)
        self.assertIsNone(parsed.meter_info.mbus_channels[5].delivered)
        self.assertEqual(parsed.decimal("1-0:1.8.1", "kWh"), Decimal("14591.819"))

    def test_requires_framing_and_electricity_reading(self) -> None:
        """Reject arbitrary framed OBIS data."""
        self.assertFalse(parser.looks_like_dsmr("/ABC5\\x\n0-0:96.1.1(foo)\n!1234"))
        with self.assertRaises(parser.InvalidTelegramError):
            parser.parse_telegram("not a telegram")


if __name__ == "__main__":
    unittest.main()

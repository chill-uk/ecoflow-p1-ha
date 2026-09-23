"""Tests for DSMR parsing."""

import unittest
from decimal import Decimal

from .helpers import ROOT, load_module

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

FLUVIUS_TELEGRAM = """/FLU5\\253770234_A\r
1-0:1.8.1(000000.915*kWh)\r
0-1:24.1.0(003)\r
0-1:96.1.1(474153313233343536)\r
0-1:24.4.0(1)\r
0-1:24.2.3(260910212004S)(04619.261*m3)\r
!0783\r
"""


# Entirely generated test data: no meter identifiers or captured telegram data.
DEMAND_TELEGRAM = (ROOT / "tests/fixtures/fluvius_demand_synthetic.txt").read_text()


class ParserTests(unittest.TestCase):
    """Verify tolerant, identifier-based parsing."""

    def test_demand_history_preserves_all_thirteen_records(self) -> None:
        """Read every triple, preserving order and raw summer/winter timestamps."""
        parsed = parser.parse_telegram(DEMAND_TELEGRAM)
        self.assertEqual(len(parsed.demand_history), 13)
        for index, record in enumerate(parsed.demand_history):
            period = f"25{index + 1:02d}01000000" if index < 12 else "260101000000"
            suffix = "S" if 3 <= index <= 9 else "W"
            self.assertEqual(record.period_timestamp, period + suffix)
            self.assertEqual(
                record.peak_kw, Decimal("4.157" if index < 12 else "4.577")
            )
        self.assertEqual(parsed.demand_history[0].peak_timestamp, "241229100000W")
        self.assertEqual(parsed.demand_history[-1].peak_timestamp, "251229100000W")

    def test_demand_history_variable_counts_and_placeholder_timestamps(self) -> None:
        """Keep raw placeholder timestamps and every declared complete record."""
        for count in (0, 1, 3, 13):
            for timestamp in ("", "000000000000W", "991332256199S", "not-a-timestamp"):
                with self.subTest(count=count, timestamp=timestamp):
                    line = f"0-0:98.1.0({count})(1-0:1.6.0)(1-0:1.6.0)"
                    line += f"({timestamp})({timestamp})(04.157*kW)" * count
                    telegram = "/FLU5\\SYNTHETIC\n1-0:1.7.0(00.123*kW)\n" + line + "\n!"
                    parsed = parser.parse_telegram(telegram)
                    self.assertEqual(len(parsed.demand_history), count)
                    for record in parsed.demand_history:
                        self.assertEqual(record.period_timestamp, timestamp)
                        self.assertEqual(record.peak_timestamp, timestamp)
                        self.assertEqual(record.peak_kw, Decimal("4.157"))

    def test_demand_history_optional_and_malformed_groups(self) -> None:
        """Bad history never invalidates the telegram or shifts record fields."""
        prefix = "0-0:98.1.0"
        headers = "(1-0:1.6.0)(1-0:1.6.0)"
        record = "(000000000000W)(250905213000S)(04.577*kW)"
        for line, count in (
            ("", 0),
            (prefix + "(0)" + headers, 0),
            (prefix + "(1)" + headers + record, 1),
            (prefix + "(2)" + headers + record, 0),
            (prefix + "(bad)" + headers + record, 0),
            (prefix + "(1)(wrong)(1-0:1.6.0)" + record, 0),
            (prefix + "(1)" + headers + "(timestamp)(04.577*kW)", 0),
        ):
            with self.subTest(line=line):
                parsed = parser.parse_telegram(
                    "/FLU5\\SYNTHETIC\n1-0:1.7.0(00.123*kW)\n" + line + "\n!"
                )
                self.assertEqual(len(parsed.demand_history), count)
                self.assertEqual(parsed.decimal("1-0:1.7.0", "kW"), Decimal("0.123"))
        for invalid in (
            "",
            "bad*kW",
            "4.577*W",
            "4.577",
            "NaN*kW",
            "Infinity*kW",
            "-1*kW",
        ):
            with self.subTest(invalid=invalid):
                line = (
                    prefix
                    + "(2)"
                    + headers
                    + record.replace("04.577*kW", invalid)
                    + record
                )
                parsed = parser.parse_telegram(
                    "/FLU5\\SYNTHETIC\n1-0:1.7.0(00.123*kW)\n" + line + "\n!"
                )
                self.assertEqual(len(parsed.demand_history), 1)
                self.assertEqual(
                    parsed.demand_history[0].period_timestamp, "000000000000W"
                )
                self.assertEqual(parsed.demand_history[0].peak_kw, Decimal("4.577"))

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

    def test_fluvius_gas_obis_variants(self) -> None:
        """Parse the Belgian e-MUCS identifiers used for gas meters."""
        parsed = parser.parse_telegram(FLUVIUS_TELEGRAM)

        channel = parsed.meter_info.mbus_channels[1]
        self.assertEqual(channel.device_type, 3)
        self.assertEqual(channel.meter_serial, "GAS123456")
        self.assertEqual(channel.timestamp, "260910212004S")
        self.assertEqual(channel.delivered, Decimal("4619.261"))
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

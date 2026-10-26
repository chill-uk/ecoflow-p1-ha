"""Tests for DSMR parsing."""

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

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

# Synthetic DSMR 4.2 Kaifa-like telegram; never includes real identifiers.
KAIFA_V4_TELEGRAM = """/KFM5KAIFA-METER\r
\r
1-3:0.2.8(42)\r
1-0:1.8.1(000123.456*kWh)\r
1-0:1.7.0(00.123*kW)\r
0-1:24.1.0(003)\r
0-1:96.1.0(3030303030303030303030303030303030)\r
0-1:24.2.1(261026190000W)(12334.675*m3)\r
!0000\r
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

    def test_dsmr4_gas_uses_legacy_upstream_mbus_fields(self) -> None:
        parsed = parser.parse_telegram(KAIFA_V4_TELEGRAM)
        gas = parsed.meter_info.mbus_channels[1]
        self.assertEqual(gas.device_type, 3)
        self.assertEqual(gas.delivered, Decimal("12334.675"))
        self.assertEqual(gas.unit, "m3")

    def test_dsmr5_gas_preserves_existing_mbus_fields(self) -> None:
        parsed = parser.parse_telegram(TELEGRAM)
        gas = parsed.meter_info.mbus_channels[5]
        self.assertEqual(gas.device_type, 3)
        self.assertEqual(gas.delivered, Decimal("11118.375"))
        self.assertEqual(gas.unit, "m3")

    def test_demand_history_uses_upstream_objects(self) -> None:
        """All 13 records have the expected timestamp, value, and unit."""
        parsed = parser.parse_telegram(DEMAND_TELEGRAM)
        self.assertEqual(len(parsed.demand_history), 13)
        local_zone = ZoneInfo("Europe/Brussels")
        for index, peak in enumerate(parsed.demand_history):
            with self.subTest(index=index):
                period_year = 2025 if index < 12 else 2026
                period_month = index + 1 if index < 12 else 1
                expected_period = datetime(
                    period_year, period_month, 1, tzinfo=local_zone
                )
                self.assertEqual(peak.datetime, expected_period.astimezone(UTC))
                self.assertEqual(peak.unit, "kW")
                self.assertEqual(
                    peak.value,
                    Decimal("4.577" if index == 12 else "4.157"),
                )
                self.assertIsNotNone(peak.occurred)
                self.assertEqual(peak.occurred.tzinfo, UTC)

        self.assertEqual(
            parsed.demand_history[0].occurred,
            datetime(2024, 12, 29, 9, tzinfo=UTC),
        )
        self.assertEqual(
            parsed.demand_history[-1].occurred,
            datetime(2025, 12, 29, 9, tzinfo=UTC),
        )

    def test_demand_history_dst_offsets(self) -> None:
        """The upstream timestamps round-trip to the correct Belgian offsets."""
        local_zone = ZoneInfo("Europe/Brussels")
        fixtures = (
            ("250301000000W", "2025-03-01T00:00:00+01:00"),
            ("250401000000S", "2025-04-01T00:00:00+02:00"),
            ("251001000000S", "2025-10-01T00:00:00+02:00"),
            ("251101000000W", "2025-11-01T00:00:00+01:00"),
        )
        for raw, expected in fixtures:
            with self.subTest(raw=raw):
                history = (
                    f"0-0:98.1.0(1)(1-0:1.6.0)(1-0:1.6.0)({raw})({raw})(04.157*kW)"
                )
                telegram = "/FLU5\\SYNTHETIC\n1-0:1.7.0(00.123*kW)\n" + history + "\n!"
                parsed = parser.parse_telegram(telegram)
                self.assertEqual(len(parsed.demand_history), 1)
                peak = parsed.demand_history[0]
                self.assertEqual(
                    peak.datetime.astimezone(local_zone).isoformat(), expected
                )
                self.assertEqual(
                    peak.occurred.astimezone(local_zone).isoformat(), expected
                )
                self.assertEqual(parsed.decimal("1-0:1.7.0", "kW"), Decimal("0.123"))

    def test_malformed_optional_history_preserves_electricity(self) -> None:
        """A malformed optional profile must not prevent valid electricity updates."""
        prefix = "0-0:98.1.0"
        headers = "(1-0:1.6.0)(1-0:1.6.0)"
        valid = "(250901000000S)(250831100000S)(04.157*kW)"
        for history in (
            "",
            prefix + "(bad)" + headers + valid,
            prefix + "(2)" + headers + valid,
            prefix + "(1)" + headers + "(991332256199S)(bad)(04.157*kW)",
            prefix + "(1)" + headers + "(250901000000S)(250831100000S)(NaN*kW)",
        ):
            with self.subTest(history=history):
                telegram = "/FLU5\\SYNTHETIC\\n1-0:1.7.0(00.123*kW)\\n"
                telegram += history + "\\n!"
                telegram = telegram.replace("\\n", "\n")
                parsed = parser.parse_telegram(telegram)
                self.assertEqual(parsed.decimal("1-0:1.7.0", "kW"), Decimal("0.123"))
                self.assertEqual(
                    len(parsed.demand_history),
                    1 if "(991332256199S)(bad)" in history else 0,
                )

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

    def test_supports_total_import_export_counters(self) -> None:
        """Support the same raw total counters as the Homey integration."""
        telegram = """/ISK5\\2M550E-1011
1-3:0.2.8(50)
1-0:1.8.0(010000.123*kWh)
1-0:2.8.0(000500.456*kWh)
!
"""

        parsed = parser.parse_telegram(telegram)

        self.assertEqual(parsed.decimal("1-0:1.8.0", "kWh"), Decimal("10000.123"))
        self.assertEqual(parsed.decimal("1-0:2.8.0", "kWh"), Decimal("500.456"))

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

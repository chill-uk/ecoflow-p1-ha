"""Tests for transient EcoFlow P1 data retention."""

from __future__ import annotations

import unittest
from decimal import Decimal

from .helpers import load_module

models = load_module("custom_components.ecoflow_p1.models")
grace = load_module("custom_components.ecoflow_p1.grace")


def _data(
    *,
    tariff: str | None = None,
    power: str | None = None,
    gas: Decimal | None = None,
) -> object:
    """Build a compact coordinator snapshot."""
    obis = {}
    if tariff is not None:
        obis["0-0:96.14.0"] = models.ObisValue((tariff,))
    if power is not None:
        obis["1-0:1.7.0"] = models.ObisValue((power,))
    channels = {}
    if gas is not None:
        channels[1] = models.MBusChannel(
            channel=1,
            device_type=3,
            delivered=gas,
            unit="m3",
        )
    return models.EcoFlowP1Data(
        telegram=models.ParsedTelegram(
            header="/ISK5\\2M550E-1011",
            obis=obis,
            meter_info=models.MeterInfo(
                manufacturer="Iskra",
                dsmr_version="5.0",
                mbus_channels=channels,
            ),
        ),
        serial="P1-123",
        firmware_version="1.1.07",
        timeout_times=10,
        crc_error_times=2,
        total_times=20,
    )


class EcoFlowP1DataGraceTests(unittest.TestCase):
    """Test bounded retention of omitted DSMR values."""

    def test_retains_value_during_one_off_omission(self) -> None:
        cache = grace.EcoFlowP1DataGrace(15)
        cache.update(_data(tariff="0002", power="00.500*kW"), 100)

        result = cache.update(_data(power="00.600*kW"), 105)

        self.assertEqual(result.telegram.decimal("0-0:96.14.0"), Decimal(2))
        self.assertEqual(
            result.telegram.decimal("1-0:1.7.0", "kW"), Decimal("0.600")
        )

    def test_expires_value_after_sustained_omission(self) -> None:
        cache = grace.EcoFlowP1DataGrace(15)
        cache.update(_data(tariff="0002", power="00.500*kW"), 100)

        result = cache.update(_data(power="00.700*kW"), 115)

        self.assertIsNone(result.telegram.decimal("0-0:96.14.0"))

    def test_reappearing_value_restarts_grace_period(self) -> None:
        cache = grace.EcoFlowP1DataGrace(15)
        cache.update(_data(tariff="0002"), 100)
        cache.update(_data(), 110)
        cache.update(_data(tariff="0001"), 112)

        result = cache.update(_data(), 126)

        self.assertEqual(result.telegram.decimal("0-0:96.14.0"), Decimal(1))

    def test_retains_mbus_reading_during_short_omission(self) -> None:
        cache = grace.EcoFlowP1DataGrace(15)
        cache.update(_data(gas=Decimal("11118.375")), 100)

        result = cache.update(_data(), 105)

        self.assertEqual(
            result.telegram.meter_info.mbus_channels[1].delivered,
            Decimal("11118.375"),
        )

    def test_failed_update_is_tolerated_inside_grace_period(self) -> None:
        self.assertTrue(grace.is_within_grace(100, 114.999, 15))

    def test_failed_update_expires_at_grace_boundary(self) -> None:
        self.assertFalse(grace.is_within_grace(100, 115, 15))
        self.assertFalse(grace.is_within_grace(None, 105, 15))


if __name__ == "__main__":
    unittest.main()

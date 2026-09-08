"""Tests for M-Bus classification."""

import unittest

from .helpers import load_module

models = load_module("custom_components.ecoflow_p1.models")
mbus = load_module("custom_components.ecoflow_p1.mbus")


class MBusTests(unittest.TestCase):
    """Verify type and unit based M-Bus classification."""

    def test_classifies_gas_water_and_energy(self) -> None:
        """Support the three exposed M-Bus measurement families."""
        cases = (
            (models.MBusChannel(1, device_type=3, unit="m3"), "gas"),
            (models.MBusChannel(2, device_type=7, unit="m3"), "water"),
            (models.MBusChannel(3, device_type=4, unit="GJ"), "energy"),
        )
        for channel, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(mbus.classify_mbus_channel(channel), expected)

    def test_energy_unit_wins_over_device_type(self) -> None:
        """Classify heat energy readings by unit rather than m3 device rules."""
        channel = models.MBusChannel(7, device_type=3, unit="kWh")
        self.assertEqual(mbus.classify_mbus_channel(channel), "energy")

    def test_unknown_combination_is_not_exposed(self) -> None:
        """Avoid assigning an incorrect device class."""
        channel = models.MBusChannel(1, device_type=15, unit="m3")
        self.assertIsNone(mbus.classify_mbus_channel(channel))

    def test_uses_homey_meter_labels(self) -> None:
        """Use consistent meter names across both P1 integrations."""
        self.assertEqual(mbus.mbus_device_type_name(3), "Gas meter")
        self.assertEqual(mbus.mbus_device_type_name(6), "Hot water meter")
        self.assertEqual(mbus.mbus_device_type_name(7), "Water meter")


if __name__ == "__main__":
    unittest.main()

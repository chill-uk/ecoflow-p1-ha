"""Tests for sensor exposure, units, defaults, and registry migration."""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from decimal import Decimal
from types import ModuleType, SimpleNamespace

from .helpers import load_module


def _install_sensor_stubs() -> None:
    """Install the Home Assistant surface required to import sensor.py."""
    homeassistant = sys.modules.setdefault("homeassistant", ModuleType("homeassistant"))
    homeassistant.__path__ = []

    components = ModuleType("homeassistant.components")
    components.__path__ = []
    sys.modules[components.__name__] = components
    sensor_component = ModuleType("homeassistant.components.sensor")

    class SensorDeviceClass:
        CURRENT = "current"
        ENERGY = "energy"
        GAS = "gas"
        POWER = "power"
        VOLTAGE = "voltage"
        WATER = "water"

    class SensorStateClass:
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"

    class SensorEntity:
        pass

    @dataclass(frozen=True, kw_only=True)
    class SensorEntityDescription:
        key: str
        translation_key: str | None = None
        device_class: str | None = None
        native_unit_of_measurement: str | None = None
        suggested_unit_of_measurement: str | None = None
        state_class: str | None = None
        entity_category: str | None = None
        entity_registry_enabled_default: bool = True
        icon: str | None = None

    sensor_component.SensorDeviceClass = SensorDeviceClass
    sensor_component.SensorEntity = SensorEntity
    sensor_component.SensorEntityDescription = SensorEntityDescription
    sensor_component.SensorStateClass = SensorStateClass
    sys.modules[sensor_component.__name__] = sensor_component

    ha_const = sys.modules.setdefault(
        "homeassistant.const", ModuleType("homeassistant.const")
    )
    ha_const.CONF_HOST = "host"
    ha_const.EntityCategory = SimpleNamespace(DIAGNOSTIC="diagnostic")
    ha_const.Platform = SimpleNamespace(SENSOR="sensor")
    ha_const.UnitOfElectricCurrent = SimpleNamespace(AMPERE="A")
    ha_const.UnitOfElectricPotential = SimpleNamespace(VOLT="V")
    ha_const.UnitOfEnergy = SimpleNamespace(KILO_WATT_HOUR="kWh")
    ha_const.UnitOfPower = SimpleNamespace(WATT="W", KILO_WATT="kW")
    ha_const.UnitOfVolume = SimpleNamespace(CUBIC_METERS="m3")

    core = sys.modules.setdefault(
        "homeassistant.core", ModuleType("homeassistant.core")
    )
    core.callback = lambda function: function
    core.HomeAssistant = object

    helpers = sys.modules.setdefault(
        "homeassistant.helpers", ModuleType("homeassistant.helpers")
    )
    helpers.__path__ = []
    device_registry = ModuleType("homeassistant.helpers.device_registry")

    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    device_registry.DeviceInfo = DeviceInfo
    device_registry.async_get = lambda _hass: None
    sys.modules[device_registry.__name__] = device_registry
    helpers.device_registry = device_registry

    entity_registry = ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda _hass: None
    sys.modules[entity_registry.__name__] = entity_registry
    helpers.entity_registry = entity_registry

    entity_platform = ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddConfigEntryEntitiesCallback = object
    sys.modules[entity_platform.__name__] = entity_platform

    update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")

    class CoordinatorEntity:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self):
            return True

    update_coordinator.CoordinatorEntity = CoordinatorEntity
    sys.modules[update_coordinator.__name__] = update_coordinator


_install_sensor_stubs()
package = sys.modules["custom_components.ecoflow_p1"]
package.EcoFlowP1ConfigEntry = object
coordinator_module = ModuleType("custom_components.ecoflow_p1.coordinator")
coordinator_module.EcoFlowP1Coordinator = object
sys.modules[coordinator_module.__name__] = coordinator_module
models = load_module("custom_components.ecoflow_p1.models")
load_module("custom_components.ecoflow_p1.mbus")
sensor = load_module("custom_components.ecoflow_p1.sensor")


def _data_with_channel(channel) -> object:
    """Create coordinator data with one M-Bus channel."""
    telegram = models.ParsedTelegram(
        header="/ISK5\\meter",
        obis={},
        meter_info=models.MeterInfo(mbus_channels={channel.channel: channel}),
    )
    return models.EcoFlowP1Data(
        telegram=telegram,
        serial="P1-123",
        firmware_version="1.1.07",
        timeout_times=1,
        crc_error_times=0,
        total_times=2,
    )


class FakeRegistry:
    """Record entity-registry migrations and removals."""

    def __init__(self, entries, registry_entries=None):
        self.entries = dict(entries)
        self.registry_entries = registry_entries or {}
        self.removed = []
        self.updated = []
        self.unit_updates = []
        self.option_updates = []

    def async_get_entity_id(self, _domain, _platform, unique_id):
        return self.entries.get(unique_id)

    def async_remove(self, entity_id):
        self.removed.append(entity_id)

    def async_get(self, entity_id):
        return self.registry_entries.get(entity_id)

    def async_update_entity(
        self, entity_id, *, new_unique_id=None, unit_of_measurement="unchanged"
    ):
        if new_unique_id is not None:
            self.updated.append((entity_id, new_unique_id))
        if unit_of_measurement != "unchanged":
            self.unit_updates.append((entity_id, unit_of_measurement))

    def async_update_entity_options(self, entity_id, domain, options):
        self.option_updates.append((entity_id, domain, options))


class SensorTests(unittest.TestCase):
    """Verify deterministic entity exposure and compatibility migrations."""

    def test_exposes_every_static_dsmr_description(self) -> None:
        """Register static DSMR entities even when a telegram omits their values."""
        data = _data_with_channel(models.MBusChannel(1, device_type=3, unit="m3"))
        descriptions = sensor._available_descriptions(data)
        keys = {description.key for description in descriptions}

        self.assertTrue(
            {description.key for description in sensor.SENSOR_DESCRIPTIONS} <= keys
        )
        for phase in (1, 2, 3):
            self.assertIn(f"voltage_l{phase}", keys)
            self.assertIn(f"current_l{phase}", keys)
            self.assertIn(f"power_import_l{phase}", keys)
            self.assertIn(f"power_export_l{phase}", keys)

    def test_all_power_descriptions_use_watts(self) -> None:
        """Keep aggregate and per-phase power readings in watts."""
        power_descriptions = [
            description
            for description in sensor.SENSOR_DESCRIPTIONS
            if description.device_class == "power"
        ]
        self.assertTrue(power_descriptions)
        for description in power_descriptions:
            with self.subTest(key=description.key):
                self.assertEqual(description.native_unit_of_measurement, "W")
                self.assertEqual(description.suggested_unit_of_measurement, "W")
                self.assertEqual(description.value_multiplier, Decimal(1000))

    def test_clears_automatic_legacy_kw_preference(self) -> None:
        """Stop Home Assistant converting native watts back to the former kW unit."""
        power = next(
            item for item in sensor.SENSOR_DESCRIPTIONS if item.key == "power_import"
        )
        unique_id = f"P1-123_{power.key}"
        registry = FakeRegistry(
            {unique_id: "sensor.power_consumption"},
            {
                "sensor.power_consumption": SimpleNamespace(
                    unit_of_measurement="kW",
                    options={
                        "sensor": {"unit_of_measurement": "kW"},
                        "sensor.private": {"suggested_unit_of_measurement": "kW"},
                    },
                )
            },
        )
        sensor.er.async_get = lambda _hass: registry

        sensor._migrate_legacy_power_units(None, "P1-123")

        self.assertEqual(
            registry.option_updates,
            [("sensor.power_consumption", "sensor.private", None)],
        )
        self.assertEqual(
            registry.unit_updates,
            [("sensor.power_consumption", None)],
        )
        self.assertEqual(
            registry.registry_entries["sensor.power_consumption"].options["sensor"],
            {"unit_of_measurement": "kW"},
        )

    def test_homey_style_diagnostic_icons(self) -> None:
        """Use the same diagnostic symbols as Homey P1."""
        descriptions = {item.key: item for item in sensor.SENSOR_DESCRIPTIONS}
        self.assertEqual(descriptions["active_tariff"].icon, "mdi:counter")
        self.assertEqual(descriptions["power_failures"].icon, "mdi:flash-alert")
        self.assertEqual(descriptions["voltage_sags_l1"].icon, "mdi:sine-wave")

    def test_l1_enabled_and_l2_l3_disabled_by_default(self) -> None:
        """Enable useful L1 readings while keeping absent phases quiet."""
        descriptions = {item.key: item for item in sensor.SENSOR_DESCRIPTIONS}
        for metric in ("voltage", "current", "power_import", "power_export"):
            self.assertTrue(
                descriptions[f"{metric}_l1"].entity_registry_enabled_default
            )
            self.assertFalse(
                descriptions[f"{metric}_l2"].entity_registry_enabled_default
            )
            self.assertFalse(
                descriptions[f"{metric}_l3"].entity_registry_enabled_default
            )

    def test_migrates_legacy_gas_unique_id(self) -> None:
        """Preserve the old entity when no replacement exists yet."""
        channel = models.MBusChannel(
            1, device_type=3, delivered=Decimal("12.3"), unit="m3"
        )
        registry = FakeRegistry({"P1-123_gas_consumption_1": "sensor.old_gas"})
        sensor.er.async_get = lambda _hass: registry

        sensor._migrate_legacy_mbus_entities(
            None, "P1-123", _data_with_channel(channel)
        )

        self.assertEqual(
            registry.updated,
            [("sensor.old_gas", "P1-123_mbus_gas_1")],
        )
        self.assertEqual(registry.removed, [])

    def test_removes_legacy_entity_when_replacement_exists(self) -> None:
        """Remove only the duplicate orphan when both IDs are registered."""
        channel = models.MBusChannel(
            1, device_type=3, delivered=Decimal("12.3"), unit="m3"
        )
        registry = FakeRegistry(
            {
                "P1-123_gas_consumption_1": "sensor.old_gas",
                "P1-123_mbus_gas_1": "sensor.gas_consumption",
            }
        )
        sensor.er.async_get = lambda _hass: registry

        sensor._migrate_legacy_mbus_entities(
            None, "P1-123", _data_with_channel(channel)
        )

        self.assertEqual(registry.updated, [])
        self.assertEqual(registry.removed, ["sensor.old_gas"])


if __name__ == "__main__":
    unittest.main()

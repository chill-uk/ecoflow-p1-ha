"""Sensor platform for the EcoFlow P1 Energy Tracker."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EcoFlowP1ConfigEntry
from .const import DOMAIN
from .coordinator import EcoFlowP1Coordinator
from .models import EcoFlowP1Data


@dataclass(frozen=True, kw_only=True)
class EcoFlowP1SensorDescription(SensorEntityDescription):
    """Describe an EcoFlow P1 sensor."""

    obis: str | None = None
    expected_unit: str | None = None
    metadata_key: str | None = None
    meter_channel: int | None = None


def _energy(key: str, name: str, obis: str) -> EcoFlowP1SensorDescription:
    return EcoFlowP1SensorDescription(
        key=key,
        name=name,
        obis=obis,
        expected_unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )


def _power(key: str, name: str, obis: str) -> EcoFlowP1SensorDescription:
    return EcoFlowP1SensorDescription(
        key=key,
        name=name,
        obis=obis,
        expected_unit="kW",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    )


def _count(key: str, name: str, obis: str) -> EcoFlowP1SensorDescription:
    return EcoFlowP1SensorDescription(
        key=key,
        name=name,
        obis=obis,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )


SENSOR_DESCRIPTIONS: tuple[EcoFlowP1SensorDescription, ...] = (
    _energy("energy_import_tariff_1", "Energy imported tariff 1", "1-0:1.8.1"),
    _energy("energy_import_tariff_2", "Energy imported tariff 2", "1-0:1.8.2"),
    _energy("energy_export_tariff_1", "Energy exported tariff 1", "1-0:2.8.1"),
    _energy("energy_export_tariff_2", "Energy exported tariff 2", "1-0:2.8.2"),
    _power("power_import", "Power imported", "1-0:1.7.0"),
    _power("power_export", "Power exported", "1-0:2.7.0"),
    EcoFlowP1SensorDescription(
        key="active_tariff", name="Active tariff", obis="0-0:96.14.0"
    ),
    _count("power_failures", "Power failures", "0-0:96.7.21"),
    _count("long_power_failures", "Long power failures", "0-0:96.7.9"),
    *tuple(
        EcoFlowP1SensorDescription(
            key=f"voltage_l{phase}",
            name=f"Voltage L{phase}",
            obis=f"1-0:{code}.7.0",
            expected_unit="V",
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            state_class=SensorStateClass.MEASUREMENT,
        )
        for phase, code in ((1, 32), (2, 52), (3, 72))
    ),
    *tuple(
        EcoFlowP1SensorDescription(
            key=f"current_l{phase}",
            name=f"Current L{phase}",
            obis=f"1-0:{code}.7.0",
            expected_unit="A",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
        )
        for phase, code in ((1, 31), (2, 51), (3, 71))
    ),
    *tuple(
        description
        for phase, import_code, export_code in (
            (1, 21, 22),
            (2, 41, 42),
            (3, 61, 62),
        )
        for description in (
            _power(
                f"power_import_l{phase}",
                f"Power imported L{phase}",
                f"1-0:{import_code}.7.0",
            ),
            _power(
                f"power_export_l{phase}",
                f"Power exported L{phase}",
                f"1-0:{export_code}.7.0",
            ),
        )
    ),
    *tuple(
        description
        for phase, code in ((1, 32), (2, 52), (3, 72))
        for description in (
            _count(
                f"voltage_sags_l{phase}", f"Voltage sags L{phase}", f"1-0:{code}.32.0"
            ),
            _count(
                f"voltage_swells_l{phase}",
                f"Voltage swells L{phase}",
                f"1-0:{code}.36.0",
            ),
        )
    ),
    EcoFlowP1SensorDescription(
        key="timeout_times",
        name="Telegram timeouts",
        metadata_key="timeout_times",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcoFlowP1SensorDescription(
        key="crc_error_times",
        name="Telegram CRC errors",
        metadata_key="crc_error_times",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcoFlowP1SensorDescription(
        key="total_times",
        name="Telegram attempts",
        metadata_key="total_times",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcoFlowP1ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors and discover optional phases or M-Bus meters later."""
    coordinator = entry.runtime_data.coordinator
    known: set[str] = set()

    @callback
    def discover_entities() -> None:
        descriptions = _available_descriptions(coordinator.data)
        new = [
            description for description in descriptions if description.key not in known
        ]
        if not new:
            return
        known.update(description.key for description in new)
        async_add_entities(
            EcoFlowP1Sensor(coordinator, entry, description) for description in new
        )

    discover_entities()
    entry.async_on_unload(coordinator.async_add_listener(discover_entities))


def _available_descriptions(data: EcoFlowP1Data) -> list[EcoFlowP1SensorDescription]:
    """Return descriptions that have appeared in the response."""
    descriptions = [
        description
        for description in SENSOR_DESCRIPTIONS
        if _value_for_description(data, description) is not None
    ]

    for channel in range(1, 5):
        obis = f"0-{channel}:24.2.1"
        if data.telegram.decimal(obis, "m3") is None:
            continue
        descriptions.append(
            EcoFlowP1SensorDescription(
                key=f"gas_consumption_{channel}",
                name="Gas consumption"
                if channel == 1
                else f"Gas consumption channel {channel}",
                obis=obis,
                expected_unit="m3",
                meter_channel=channel,
                device_class=SensorDeviceClass.GAS,
                native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
                state_class=SensorStateClass.TOTAL_INCREASING,
            )
        )
    return descriptions


def _value_for_description(
    data: EcoFlowP1Data, description: EcoFlowP1SensorDescription
) -> Decimal | int | None:
    """Read the current value described by an entity description."""
    if description.metadata_key is not None:
        value = getattr(data, description.metadata_key, None)
        return value if isinstance(value, int) else None
    if description.obis is None:
        return None
    return data.telegram.decimal(description.obis, description.expected_unit)


class EcoFlowP1Sensor(CoordinatorEntity[EcoFlowP1Coordinator], SensorEntity):
    """Representation of one EcoFlow P1 measurement."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcoFlowP1Coordinator,
        entry: EcoFlowP1ConfigEntry,
        description: EcoFlowP1SensorDescription,
    ) -> None:
        """Initialize an EcoFlow P1 sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer="EcoFlow",
            model="P1 Energy Tracker",
            name="EcoFlow P1 Energy Tracker",
            serial_number=coordinator.data.serial,
            sw_version=coordinator.data.firmware_version,
            configuration_url=f"http://{coordinator.api.host}/",
        )

    @property
    def native_value(self) -> Decimal | int | None:
        """Return the latest sensor value."""
        return _value_for_description(self.coordinator.data, self.entity_description)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the relevant physical meter identifier."""
        info = self.coordinator.data.telegram.meter_info
        if self.entity_description.meter_channel is not None:
            channel = self.entity_description.meter_channel
            attributes: dict[str, Any] = {"mbus_channel": channel}
            if serial := info.mbus_serials.get(channel):
                attributes["meter_serial"] = serial
            if device_type := info.mbus_types.get(channel):
                attributes["mbus_device_type"] = device_type
            return attributes
        if self.entity_description.metadata_key is None and info.electricity_serial:
            return {"meter_serial": info.electricity_serial}
        return None

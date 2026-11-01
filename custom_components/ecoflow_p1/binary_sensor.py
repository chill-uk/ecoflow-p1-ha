"""Optional P1 device-status binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EcoFlowP1ConfigEntry
from .status import P1StatusCoordinator


async def async_setup_entry(
    hass, entry: EcoFlowP1ConfigEntry, async_add_entities
) -> None:
    """Register status entities on the existing P1 device."""
    base_id = entry.unique_id or entry.entry_id
    coordinator = entry.runtime_data.status_coordinator
    async_add_entities(
        [
            P1StatusBinarySensor(coordinator, base_id, "discoverable"),
            P1StatusBinarySensor(coordinator, base_id, "mqtt_connected"),
        ]
    )


class P1StatusBinarySensor(CoordinatorEntity[P1StatusCoordinator], BinarySensorEntity):
    """A read-only P1 firmware diagnostic flag."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: P1StatusCoordinator, base_id: str, key: str
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{base_id}_{key}"
        self._attr_translation_key = key
        if key == "mqtt_connected":
            self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_device_info = {"identifiers": {("ecoflow_p1", base_id)}}

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and (getattr(self.coordinator.data, self._key) is not None)
        )

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return getattr(self.coordinator.data, self._key)

"""Diagnostics support for EcoFlow P1."""

from __future__ import annotations

from typing import Any

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from . import EcoFlowP1ConfigEntry
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EcoFlowP1ConfigEntry
) -> dict[str, Any]:
    """Return safe metadata and encrypted support records."""
    coordinator = entry.runtime_data.coordinator
    integration = await async_get_integration(hass, DOMAIN)
    capture = coordinator.encrypted_capture.diagnostics()
    encrypted_records = capture.pop("encrypted_records")

    return {
        "schema_version": 1,
        "integration_version": integration.version,
        "home_assistant_version": HA_VERSION,
        "firmware_version": (
            coordinator.data.firmware_version if coordinator.data is not None else None
        ),
        "phase_mode": coordinator.phase_mode,
        "capture": capture,
        "encrypted_records": encrypted_records,
    }

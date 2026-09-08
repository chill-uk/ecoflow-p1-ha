"""EcoFlow P1 Energy Tracker integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EcoFlowP1Api
from .const import PLATFORMS
from .coordinator import EcoFlowP1Coordinator


@dataclass(slots=True)
class EcoFlowP1RuntimeData:
    """Runtime data for an EcoFlow P1 config entry."""

    coordinator: EcoFlowP1Coordinator


type EcoFlowP1ConfigEntry = ConfigEntry[EcoFlowP1RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: EcoFlowP1ConfigEntry) -> bool:
    """Set up EcoFlow P1 from a config entry."""
    api = EcoFlowP1Api(async_get_clientsession(hass), entry.data[CONF_HOST])
    coordinator = EcoFlowP1Coordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = EcoFlowP1RuntimeData(coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcoFlowP1ConfigEntry) -> bool:
    """Unload an EcoFlow P1 config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: EcoFlowP1ConfigEntry
) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)

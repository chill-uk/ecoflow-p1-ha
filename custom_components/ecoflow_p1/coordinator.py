"""Data coordinator for the EcoFlow P1 Energy Tracker."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EcoFlowP1Api, EcoFlowP1Error
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .models import EcoFlowP1Data

_LOGGER = logging.getLogger(__name__)


class EcoFlowP1Coordinator(DataUpdateCoordinator[EcoFlowP1Data]):
    """Coordinate a single request shared by all EcoFlow P1 entities."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: EcoFlowP1Api,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
            always_update=True,
        )

    async def _async_update_data(self) -> EcoFlowP1Data:
        """Fetch the latest local telegram and metadata."""
        try:
            return await self.api.async_get_data()
        except EcoFlowP1Error as err:
            raise UpdateFailed(f"Error communicating with EcoFlow P1: {err}") from err

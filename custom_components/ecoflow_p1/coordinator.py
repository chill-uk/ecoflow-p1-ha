"""Data coordinator for the EcoFlow P1 Energy Tracker."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EcoFlowP1Api, EcoFlowP1Error
from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    TRANSIENT_FAILURE_GRACE_SECONDS,
)
from .grace import EcoFlowP1DataGrace, is_within_grace
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
        self._last_success_at: float | None = None
        self._data_grace = EcoFlowP1DataGrace(TRANSIENT_FAILURE_GRACE_SECONDS)
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
        loop = asyncio.get_running_loop()
        try:
            incoming = await self.api.async_get_data()
        except EcoFlowP1Error as err:
            if (
                is_within_grace(
                    self._last_success_at,
                    loop.time(),
                    TRANSIENT_FAILURE_GRACE_SECONDS,
                )
                and self.data is not None
            ):
                _LOGGER.debug(
                    "Retaining the last EcoFlow P1 data during a transient error: %s",
                    err,
                )
                return self.data
            raise UpdateFailed(f"Error communicating with EcoFlow P1: {err}") from err

        self._last_success_at = loop.time()
        return self._data_grace.update(incoming, self._last_success_at)

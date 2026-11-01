"""Optional read-only device status, independent of DSMR polling."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import EcoFlowP1Client

_LOGGER = logging.getLogger(__name__)
MAC_RE = re.compile(r"^[0-9a-fA-F]{12}$")


def normalize_mac(value: object) -> str | None:
    """Accept a 12-hex-digit MAC; reject invalid or multicast addresses."""
    if not isinstance(value, str):
        return None
    compact = value.replace(":", "").replace("-", "")
    if not MAC_RE.fullmatch(compact):
        return None
    octets = bytes.fromhex(compact)
    if octets[0] & 1 or octets == b"\x00" * 6:
        return None
    return ":".join(f"{b:02X}" for b in octets)


@dataclass(frozen=True, slots=True)
class P1DeviceStatus:
    discoverable: bool | None = None
    wifi_rssi: int | None = None
    mqtt_connected: bool | None = None
    mac: str | None = None


class P1StatusCoordinator(DataUpdateCoordinator[P1DeviceStatus]):
    """Poll P1 device diagnostic endpoints every minute, independently."""

    def __init__(self, hass: HomeAssistant, client: EcoFlowP1Client) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="EcoFlow P1 device status",
            update_interval=timedelta(seconds=60),
        )
        self.client = client

    async def _async_update_data(self) -> P1DeviceStatus:
        paths = (
            "/rpc/Shelly.GetDeviceInfo",
            "/rpc/WiFi.GetStatus",
            "/rpc/MQTT.GetStatus",
        )
        results = await asyncio.gather(
            *(self.client.async_get_json(path) for path in paths),
            return_exceptions=True,
        )
        previous = self.data or P1DeviceStatus()
        values = []
        for path, result in zip(paths, results, strict=True):
            if isinstance(result, BaseException):
                _LOGGER.debug("Optional P1 status %s unavailable: %s", path, result)
                values.append(None)
            else:
                values.append(result)
        device, wifi, mqtt = values
        # Preserve known identity on a transient failure. Other fields must
        # become unavailable rather than show stale connectivity readings.
        return P1DeviceStatus(
            discoverable=(
                device.get("discoverable")
                if isinstance(device, dict) and type(device.get("discoverable")) is bool
                else None
            ),
            wifi_rssi=(
                wifi.get("rssi")
                if isinstance(wifi, dict)
                and type(wifi.get("rssi")) is int
                and -127 <= wifi["rssi"] <= 0
                else None
            ),
            mqtt_connected=(
                mqtt.get("connected")
                if isinstance(mqtt, dict) and type(mqtt.get("connected")) is bool
                else None
            ),
            mac=(
                normalize_mac(device.get("mac"))
                if isinstance(device, dict) and normalize_mac(device.get("mac"))
                else previous.mac
            ),
        )

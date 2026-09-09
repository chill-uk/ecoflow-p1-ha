"""Bounded retention for transient EcoFlow P1 data gaps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from .models import EcoFlowP1Data, MBusChannel, MeterInfo, ObisValue, ParsedTelegram


def is_within_grace(
    last_success_at: float | None,
    now: float,
    grace_seconds: float,
) -> bool:
    """Return whether a failed update is still inside the grace period."""
    return last_success_at is not None and now - last_success_at < grace_seconds


class ExpiringMap[_KeyT, _ValueT]:
    """Keep recently seen values while expiring genuinely stale entries."""

    def __init__(self, grace_seconds: float) -> None:
        """Initialize the cache."""
        self._grace_seconds = grace_seconds
        self._data: dict[_KeyT, _ValueT] = {}
        self._last_seen: dict[_KeyT, float] = {}

    def update(
        self,
        incoming: Mapping[_KeyT, _ValueT],
        now: float,
    ) -> dict[_KeyT, _ValueT]:
        """Merge current values and expire entries missing beyond the grace period."""
        for key, value in incoming.items():
            self._data[key] = value
            self._last_seen[key] = now

        for key in tuple(self._data):
            if key in incoming:
                continue
            if now - self._last_seen[key] >= self._grace_seconds:
                self._data.pop(key)
                self._last_seen.pop(key)

        return self._data.copy()


class EcoFlowP1DataGrace:
    """Retain optional fields missing from short-lived partial responses."""

    def __init__(self, grace_seconds: float) -> None:
        """Initialize independent caches for readings and metadata."""
        self._obis = ExpiringMap[str, ObisValue](grace_seconds)
        self._mbus = ExpiringMap[int, MBusChannel](grace_seconds)
        self._metadata = ExpiringMap[str, object](grace_seconds)

    def update(self, incoming: EcoFlowP1Data, now: float) -> EcoFlowP1Data:
        """Return a snapshot supplemented with values seen within the grace period."""
        info = incoming.telegram.meter_info
        obis = self._obis.update(incoming.telegram.obis, now)
        mbus_channels = self._mbus.update(
            {
                channel: value
                for channel, value in info.mbus_channels.items()
                if value.delivered is not None
            },
            now,
        )
        metadata = self._metadata.update(
            {
                key: value
                for key, value in {
                    "serial": incoming.serial,
                    "firmware_version": incoming.firmware_version,
                    "timeout_times": incoming.timeout_times,
                    "crc_error_times": incoming.crc_error_times,
                    "total_times": incoming.total_times,
                    "manufacturer": info.manufacturer,
                    "model": info.model,
                    "dsmr_version": info.dsmr_version,
                    "electricity_equipment_id": info.electricity_equipment_id,
                    "electricity_serial": info.electricity_serial,
                }.items()
                if value is not None
            },
            now,
        )

        meter_info = MeterInfo(
            manufacturer=cast(str | None, metadata.get("manufacturer")),
            model=cast(str | None, metadata.get("model")),
            dsmr_version=cast(str | None, metadata.get("dsmr_version")),
            electricity_equipment_id=cast(
                str | None, metadata.get("electricity_equipment_id")
            ),
            electricity_serial=cast(
                str | None, metadata.get("electricity_serial")
            ),
            mbus_channels=mbus_channels,
        )
        telegram = ParsedTelegram(
            header=incoming.telegram.header,
            obis=obis,
            meter_info=meter_info,
        )
        return EcoFlowP1Data(
            telegram=telegram,
            serial=cast(str | None, metadata.get("serial")),
            firmware_version=cast(str | None, metadata.get("firmware_version")),
            timeout_times=cast(int | None, metadata.get("timeout_times")),
            crc_error_times=cast(int | None, metadata.get("crc_error_times")),
            total_times=cast(int | None, metadata.get("total_times")),
        )

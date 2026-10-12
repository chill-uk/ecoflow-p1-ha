"""Compatibility wrappers for shared DSMR M-Bus helpers."""

from __future__ import annotations

from p1_dsmr_common.mbus import (
    MbusMeasurementKind,
    classify_mbus_measurement,
    mbus_device_type_name,
)

from .models import MBusChannel

MBusKind = MbusMeasurementKind


def classify_mbus_channel(channel: MBusChannel) -> MBusKind | None:
    """Classify a channel using shared DSMR M-Bus semantics."""
    return classify_mbus_measurement(channel.device_type, channel.unit)


__all__ = [
    "MBusKind",
    "classify_mbus_channel",
    "mbus_device_type_name",
]

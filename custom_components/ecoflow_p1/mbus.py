"""M-Bus classification helpers."""

from __future__ import annotations

from typing import Final, Literal

from .models import MBusChannel

MBusKind = Literal["gas", "water", "energy"]

_ENERGY_UNITS: Final = {"j", "kj", "mj", "gj", "wh", "kwh", "mwh"}
_METER_TYPE_NAMES: Final = {
    0: "Other",
    1: "Oil",
    2: "Electricity",
    3: "Gas",
    4: "Heat",
    5: "Steam",
    6: "Warm water",
    7: "Water",
    8: "Heat cost allocator",
    9: "Compressed air",
    10: "Cooling load meter (outlet)",
    11: "Cooling load meter (inlet)",
    12: "Heat (inlet)",
    13: "Heat/cooling",
    14: "Bus/system",
    15: "Unknown",
}


def classify_mbus_channel(channel: MBusChannel) -> MBusKind | None:
    """Classify a channel using its unit and DSMR M-Bus device type."""
    unit = channel.unit.casefold() if channel.unit else None
    if unit in _ENERGY_UNITS:
        return "energy"
    if unit != "m3":
        return None
    if channel.device_type == 3:
        return "gas"
    if channel.device_type in (6, 7):
        return "water"
    return None


def mbus_device_type_name(device_type: int | None) -> str | None:
    """Return the standard M-Bus device type label."""
    if device_type is None:
        return None
    return _METER_TYPE_NAMES.get(device_type, f"Type {device_type}")

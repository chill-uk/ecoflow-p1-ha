"""Data models for the EcoFlow P1 Energy Tracker integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True, slots=True)
class ObisValue:
    """A parsed OBIS value."""

    values: tuple[str, ...]

    @property
    def value(self) -> str | None:
        """Return the final group, which contains standard OBIS readings."""
        return self.values[-1] if self.values else None


@dataclass(frozen=True, slots=True)
class MBusChannel:
    """Information and the latest reading for one discovered M-Bus channel."""

    channel: int
    device_type: int | None = None
    equipment_id: str | None = None
    meter_serial: str | None = None
    timestamp: str | None = None
    delivered: Decimal | None = None
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class MeterInfo:
    """Information discovered inside the DSMR telegram."""

    manufacturer: str | None = None
    model: str | None = None
    dsmr_version: str | None = None
    electricity_equipment_id: str | None = None
    electricity_serial: str | None = None
    mbus_channels: dict[int, MBusChannel] = field(default_factory=dict)

    @property
    def protocol_family(self) -> str | None:
        """Return the protocol family inferred from the DSMR version."""
        if self.dsmr_version is None:
            return None
        return "DSMR"


@dataclass(frozen=True, slots=True)
class ParsedTelegram:
    """A parsed DSMR telegram."""

    header: str
    obis: dict[str, ObisValue]
    meter_info: MeterInfo

    def decimal(
        self, identifier: str, expected_unit: str | None = None
    ) -> Decimal | None:
        """Return a numeric OBIS value, or None when absent or malformed."""
        item = self.obis.get(identifier)
        if item is None or item.value is None:
            return None

        parsed = split_number_and_unit(item.value)
        if parsed is None:
            return None
        value, unit = parsed
        if expected_unit is not None and (
            unit is None or unit.casefold() != expected_unit.casefold()
        ):
            return None
        return value


@dataclass(frozen=True, slots=True)
class EcoFlowP1Data:
    """A complete response from the EcoFlow P1."""

    telegram: ParsedTelegram
    serial: str | None
    firmware_version: str | None
    timeout_times: int | None
    crc_error_times: int | None
    total_times: int | None
    raw_telegram: str = ""


def split_number_and_unit(value: str) -> tuple[Decimal, str | None] | None:
    """Split a DSMR numeric value and optional unit without raising."""
    number, separator, unit = value.rpartition("*")
    if not separator:
        number = value
        unit = ""
    try:
        parsed = Decimal(number)
    except (InvalidOperation, ValueError):
        return None
    return parsed, unit or None

"""Data models for the EcoFlow P1 Energy Tracker integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ObisValue:
    """A parsed OBIS value."""

    values: tuple[str, ...]

    @property
    def value(self) -> str | None:
        """Return the last group, which contains the reading for standard fields."""
        return self.values[-1] if self.values else None


@dataclass(frozen=True, slots=True)
class MeterInfo:
    """Information discovered inside the DSMR telegram."""

    electricity_serial: str | None = None
    mbus_serials: dict[int, str] = field(default_factory=dict)
    mbus_types: dict[int, str] = field(default_factory=dict)


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

        raw_value = item.value
        if "*" in raw_value:
            value, unit = raw_value.rsplit("*", 1)
            if (
                expected_unit is not None
                and unit.casefold() != expected_unit.casefold()
            ):
                return None
        else:
            value = raw_value
            if expected_unit is not None:
                return None

        try:
            return Decimal(value)
        except (ValueError, ArithmeticError):
            return None


@dataclass(frozen=True, slots=True)
class EcoFlowP1Data:
    """A complete response from the EcoFlow P1."""

    telegram: ParsedTelegram
    serial: str | None
    firmware_version: str | None
    timeout_times: int | None
    crc_error_times: int | None
    total_times: int | None

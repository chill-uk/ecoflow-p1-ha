"""Small, tolerant parser for DSMR telegrams exposed by the EcoFlow P1."""

from __future__ import annotations

import re
import string
from decimal import Decimal

from .models import (
    MBusChannel,
    MeterInfo,
    ObisValue,
    ParsedTelegram,
    split_number_and_unit,
)

_OBIS_LINE = re.compile(
    r"^(?P<identifier>\d+-\d+:\d+\.\d+\.\d+)(?P<groups>(?:\([^()]*(?:\*[^()]*)?\))+)$"
)
_GROUP = re.compile(r"\(([^()]*)\)")
_HEADER = re.compile(r"^/(?P<manufacturer>[A-Za-z]{3})\d(?P<model>.*)$")
_MBUS_IDENTIFIER = re.compile(
    r"^0-(?P<channel>\d+):(?P<field>24\.1\.0|96\.1\.0|24\.2\.1)$"
)
_READING_IDENTIFIERS = frozenset(
    {
        "1-0:1.8.1",
        "1-0:1.8.2",
        "1-0:2.8.1",
        "1-0:2.8.2",
        "1-0:1.7.0",
        "1-0:2.7.0",
    }
)
_PRINTABLE = frozenset(string.printable) - frozenset("\r\n\t\x0b\x0c")


class InvalidTelegramError(ValueError):
    """Raised when content is not recognisable as a DSMR telegram."""


def looks_like_dsmr(telegram: str) -> bool:
    """Return whether content has DSMR framing and an electricity reading."""
    if not isinstance(telegram, str):
        return False

    lines = [line.strip() for line in telegram.splitlines() if line.strip()]
    if len(lines) < 3 or not lines[0].startswith("/"):
        return False
    if not any(line.startswith("!") for line in lines[1:]):
        return False
    return any(
        (match := _OBIS_LINE.fullmatch(line))
        and match.group("identifier") in _READING_IDENTIFIERS
        for line in lines[1:]
    )


def parse_telegram(telegram: str) -> ParsedTelegram:
    """Parse a DSMR telegram by OBIS identifier.

    Unknown lines and individually malformed optional fields are ignored.
    """
    if not looks_like_dsmr(telegram):
        raise InvalidTelegramError("Response does not look like a DSMR telegram")

    lines = [line.strip() for line in telegram.splitlines() if line.strip()]
    parsed: dict[str, ObisValue] = {}

    for line in lines[1:]:
        if line.startswith("!"):
            break
        match = _OBIS_LINE.fullmatch(line)
        if match is None:
            continue
        groups = tuple(_GROUP.findall(match.group("groups")))
        if groups:
            parsed[match.group("identifier")] = ObisValue(groups)

    manufacturer, model = _parse_header(lines[0])
    equipment_id = _plain_value(parsed, "0-0:96.1.1") or _plain_value(
        parsed, "0-0:96.1.0"
    )

    return ParsedTelegram(
        header=lines[0],
        obis=parsed,
        meter_info=MeterInfo(
            manufacturer=manufacturer,
            model=model,
            dsmr_version=_format_dsmr_version(_plain_value(parsed, "1-3:0.2.8")),
            electricity_equipment_id=equipment_id,
            electricity_serial=_decode_equipment_id(equipment_id),
            mbus_channels=_parse_mbus_channels(parsed),
        ),
    )


def _parse_header(header: str) -> tuple[str | None, str | None]:
    """Extract the DSMR manufacturer code and meter model from a header."""
    match = _HEADER.match(header)
    if match is None:
        return None, None
    model = match.group("model").strip().lstrip("\\")
    return match.group("manufacturer").upper(), model or None


def _format_dsmr_version(value: str | None) -> str | None:
    """Format DSMR's compact version value, such as 50, as 5.0."""
    if value is None:
        return None
    compact = value.strip()
    if compact.isdigit() and len(compact) == 2:
        return f"{compact[0]}.{compact[1]}"
    return compact or None


def _parse_mbus_channels(values: dict[str, ObisValue]) -> dict[int, MBusChannel]:
    """Discover and parse every M-Bus channel present in the telegram."""
    channels = {
        int(match.group("channel"))
        for identifier in values
        if (match := _MBUS_IDENTIFIER.fullmatch(identifier)) is not None
    }
    result: dict[int, MBusChannel] = {}
    for channel in sorted(channels):
        equipment_id = _plain_value(values, f"0-{channel}:96.1.0")
        timestamp, delivered, unit = _parse_mbus_reading(
            values.get(f"0-{channel}:24.2.1")
        )
        result[channel] = MBusChannel(
            channel=channel,
            device_type=_parse_device_type(_plain_value(values, f"0-{channel}:24.1.0")),
            equipment_id=equipment_id,
            meter_serial=_decode_equipment_id(equipment_id),
            timestamp=timestamp,
            delivered=delivered,
            unit=unit,
        )
    return result


def _parse_mbus_reading(
    value: ObisValue | None,
) -> tuple[str | None, Decimal | None, str | None]:
    """Parse timestamp, value, and unit from an M-Bus delivered reading."""
    if value is None or not value.values:
        return None, None, None
    reading = split_number_and_unit(value.values[-1])
    if reading is None:
        return value.values[0] or None, None, None
    delivered, unit = reading
    timestamp = value.values[-2] if len(value.values) > 1 else None
    return timestamp or None, delivered, unit


def _parse_device_type(value: str | None) -> int | None:
    """Parse a DSMR M-Bus device type without failing the telegram."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _decode_equipment_id(value: str | None) -> str | None:
    """Decode hexadecimal equipment IDs when they contain printable ASCII."""
    if not value:
        return None
    compact = value.strip()
    if len(compact) % 2 or not all(char in string.hexdigits for char in compact):
        return compact
    try:
        decoded = bytes.fromhex(compact).decode("ascii").rstrip("\x00 ")
    except (UnicodeDecodeError, ValueError):
        return compact
    if decoded and all(char in _PRINTABLE for char in decoded):
        return decoded
    return compact


def _plain_value(values: dict[str, ObisValue], identifier: str) -> str | None:
    """Return a non-empty group without a unit."""
    item = values.get(identifier)
    if item is None or item.value is None or "*" in item.value:
        return None
    return item.value or None

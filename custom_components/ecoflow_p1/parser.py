"""Small, tolerant parser for DSMR telegrams exposed by the EcoFlow P1."""

from __future__ import annotations

import re

from .models import MeterInfo, ObisValue, ParsedTelegram

_OBIS_LINE = re.compile(
    r"^(?P<identifier>\d+-\d+:\d+\.\d+\.\d+)(?P<groups>(?:\([^()]*(?:\*[^()]*)?\))+)$"
)
_GROUP = re.compile(r"\(([^()]*)\)")


class InvalidTelegramError(ValueError):
    """Raised when content is not recognisable as a DSMR telegram."""


def looks_like_dsmr(telegram: str) -> bool:
    """Return whether content has DSMR framing and at least one OBIS line."""
    if not isinstance(telegram, str):
        return False

    lines = [line.strip() for line in telegram.splitlines() if line.strip()]
    if len(lines) < 3 or not lines[0].startswith("/"):
        return False
    if not any(line.startswith("!") for line in lines[1:]):
        return False
    return any(_OBIS_LINE.fullmatch(line) for line in lines[1:])


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

    electricity_serial = _plain_value(parsed, "0-0:96.1.1")
    mbus_serials: dict[int, str] = {}
    mbus_types: dict[int, str] = {}
    for channel in range(1, 5):
        if serial := _plain_value(parsed, f"0-{channel}:96.1.0"):
            mbus_serials[channel] = serial
        if device_type := _plain_value(parsed, f"0-{channel}:24.1.0"):
            mbus_types[channel] = device_type

    return ParsedTelegram(
        header=lines[0],
        obis=parsed,
        meter_info=MeterInfo(
            electricity_serial=electricity_serial,
            mbus_serials=mbus_serials,
            mbus_types=mbus_types,
        ),
    )


def _plain_value(values: dict[str, ObisValue], identifier: str) -> str | None:
    """Return a non-empty group without a unit."""
    item = values.get(identifier)
    if item is None or item.value is None or "*" in item.value:
        return None
    return item.value or None

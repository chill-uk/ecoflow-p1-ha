"""Parse DSMR telegrams exposed by the EcoFlow P1."""

from __future__ import annotations

import re
import string
from decimal import Decimal
from typing import Any

from dsmr_parser import telegram_specifications
from dsmr_parser.exceptions import ParseError
from dsmr_parser.parsers import TelegramParser

from .extensions import parse_demand_history
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
_MBUS_READING = re.compile(
    r"^0-(?P<channel>\d+):24\.2\.[13]\((?P<timestamp>[^)]*)\)",
    re.MULTILINE,
)
_READING_IDENTIFIERS = frozenset(
    {
        "1-0:1.8.0",
        "1-0:2.8.0",
        "1-0:1.8.1",
        "1-0:1.8.2",
        "1-0:2.8.1",
        "1-0:2.8.2",
        "1-0:1.7.0",
        "1-0:2.7.0",
    }
)
_PRINTABLE = frozenset(string.printable) - frozenset("\r\n\t\x0b\x0c")

_PARSERS = {
    "3": TelegramParser(telegram_specifications.V3, apply_checksum_validation=False),
    "4": TelegramParser(telegram_specifications.V4, apply_checksum_validation=False),
    "5": TelegramParser(telegram_specifications.V5, apply_checksum_validation=False),
}
_FLUVIUS_PARSER = TelegramParser(
    telegram_specifications.BELGIUM_FLUVIUS,
    apply_checksum_validation=False,
)


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
    """Parse a DSMR telegram while preserving the integration's public model.

    Standard DSMR interpretation is delegated to dsmr-parser. The raw OBIS map
    remains available because released EcoFlow entities address values by OBIS
    identifier, and changing that contract would risk entity behavior.
    """
    if not looks_like_dsmr(telegram):
        raise InvalidTelegramError("Response does not look like a DSMR telegram")

    lines = [line.strip() for line in telegram.splitlines() if line.strip()]
    obis_values = _raw_obis_values(lines)

    try:
        parsed = _select_parser(lines[0], obis_values).parse(
            _parser_safe_telegram(telegram)
        )
    except ParseError as err:
        raise InvalidTelegramError("Unable to parse DSMR telegram") from err

    manufacturer, model = _parse_header(lines[0])
    equipment = getattr(parsed, "EQUIPMENT_IDENTIFIER", None)
    if equipment is not None:
        equipment_id = str(equipment.value)
    else:
        equipment_id = _first_plain_value(
            obis_values,
            "0-0:96.1.1",
            "0-0:96.1.0",
        )

    return ParsedTelegram(
        header=lines[0],
        obis=obis_values,
        demand_history=parse_demand_history(obis_values.get("0-0:98.1.0")),
        meter_info=MeterInfo(
            manufacturer=manufacturer,
            model=model,
            dsmr_version=_format_dsmr_version(_plain_value(obis_values, "1-3:0.2.8")),
            electricity_equipment_id=equipment_id,
            electricity_serial=_decode_equipment_id(equipment_id),
            mbus_channels=_parse_mbus_channels(parsed, telegram),
        ),
    )


def _select_parser(
    header: str, values: dict[str, ObisValue]
) -> TelegramParser:
    """Select the closest dsmr-parser specification for the telegram."""
    manufacturer, _ = _parse_header(header)
    if manufacturer == "FLU":
        return _FLUVIUS_PARSER

    version = _plain_value(values, "1-3:0.2.8")
    return _PARSERS.get((version or "5")[:1], _PARSERS["5"])


def _raw_obis_values(lines: list[str]) -> dict[str, ObisValue]:
    """Retain raw grouped values for the integration's released OBIS contract."""
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
    return parsed


def _parse_mbus_channels(parsed: Any, raw_telegram: str) -> dict[int, MBusChannel]:
    """Normalize dsmr-parser M-Bus devices into the existing model."""
    devices = getattr(parsed, "MBUS_DEVICES", None)
    if not devices:
        return {}

    timestamps = {
        int(match.group("channel")): match.group("timestamp") or None
        for match in _MBUS_READING.finditer(
            raw_telegram.replace("\r\n", "\n").replace("\r", "\n")
        )
    }
    result: dict[int, MBusChannel] = {}

    for device in devices:
        channel = int(device.channel_id)
        device_type = getattr(device, "MBUS_DEVICE_TYPE", None)
        equipment = getattr(device, "MBUS_EQUIPMENT_IDENTIFIER", None)
        reading = getattr(device, "MBUS_METER_READING", None)

        equipment_id = str(equipment.value) if equipment is not None else None
        delivered = reading.value if reading is not None else None
        unit = reading.unit if reading is not None else None

        result[channel] = MBusChannel(
            channel=channel,
            device_type=int(device_type.value) if device_type is not None else None,
            equipment_id=equipment_id,
            meter_serial=_decode_equipment_id(equipment_id),
            timestamp=timestamps.get(channel),
            delivered=delivered if isinstance(delivered, Decimal) else None,
            unit=unit,
        )

    return result


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


def _first_plain_value(values: dict[str, ObisValue], *identifiers: str) -> str | None:
    """Return the first non-empty plain value from equivalent OBIS identifiers."""
    for identifier in identifiers:
        if (value := _plain_value(values, identifier)) is not None:
            return value
    return None


def _parser_safe_telegram(telegram: str) -> str:
    """Remove malformed optional extensions before invoking dsmr-parser.

    EcoFlow historically treats malformed optional fields as absent rather than
    rejecting an otherwise valid telegram. Preserve that contract while still
    using dsmr-parser for standard DSMR interpretation.
    """
    safe_lines: list[str] = []
    for line in telegram.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()

        # Fluvius 13-month demand history is parsed separately so raw placeholder
        # timestamps remain available and malformed history cannot shift records.
        if stripped.startswith("0-0:98.1.0("):
            continue

        match = _OBIS_LINE.fullmatch(stripped)
        if match and re.fullmatch(r"0-\d+:24\.2\.[13]", match.group("identifier")):
            groups = tuple(_GROUP.findall(match.group("groups")))
            reading = split_number_and_unit(groups[-1]) if groups else None
            if reading is None:
                continue

        safe_lines.append(line)

    return _normalize_line_endings("\n".join(safe_lines))


def _normalize_line_endings(telegram: str) -> str:
    """Normalize local HTTP content to the CRLF expected by dsmr-parser."""
    normalized = telegram.replace("\r\n", "\n").replace("\r", "\n")
    return "\r\n".join(normalized.split("\n"))

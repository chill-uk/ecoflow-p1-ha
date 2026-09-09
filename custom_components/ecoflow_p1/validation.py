"""CRC, required-field validation, and safe logging for DSMR telegrams."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final

_CRC = re.compile(r"!([0-9A-Fa-f]{4})(?:\r?\n)?$")
_OBIS_PREFIX = re.compile(r"^(\d+-\d+:\d+\.\d+\.\d+)")
_OBIS_LINE = re.compile(
    r"^(?P<identifier>\d+-\d+:\d+\.\d+\.\d+)"
    r"(?P<groups>(?:\([^()]*\))+)$"
)
_GROUP = re.compile(r"\(([^()]*)\)")
_TIMESTAMP = re.compile(r"^\d{12}[SW]$")
_EQUIPMENT_ID = re.compile(r"^(0-\d+:96\.1\.[01])\([^()]*\)\r?$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class CrcResult:
    """Result of validating a telegram's reported CRC."""

    reported: str | None
    calculated: str | None
    valid: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ObisRule:
    """Expected shape of one continuous DSMR field."""

    name: str
    kind: str
    unit: str | None = None
    allowed: frozenset[int] | None = None


@dataclass(frozen=True, slots=True)
class TelegramValidation:
    """Required fields missing from or invalid in one raw telegram."""

    missing: tuple[str, ...]
    invalid: dict[str, str]

    @property
    def valid(self) -> bool:
        """Return whether every required field passed validation."""
        return not self.missing and not self.invalid


_COMMON_RULES: Final[dict[str, ObisRule]] = {
    "1-3:0.2.8": ObisRule("DSMR version", "version"),
    "0-0:1.0.0": ObisRule("Telegram timestamp", "timestamp"),
    "0-0:96.1.1": ObisRule("Electricity meter ID", "text"),
    "1-0:1.8.1": ObisRule("Imported energy tariff 1", "decimal", "kWh"),
    "1-0:1.8.2": ObisRule("Imported energy tariff 2", "decimal", "kWh"),
    "1-0:2.8.1": ObisRule("Exported energy tariff 1", "decimal", "kWh"),
    "1-0:2.8.2": ObisRule("Exported energy tariff 2", "decimal", "kWh"),
    "0-0:96.14.0": ObisRule(
        "Active tariff", "integer", allowed=frozenset({1, 2})
    ),
    "1-0:1.7.0": ObisRule("Total imported power", "decimal", "kW"),
    "1-0:2.7.0": ObisRule("Total exported power", "decimal", "kW"),
}

_PHASE_RULES: Final[dict[int, dict[str, ObisRule]]] = {
    phase: {
        f"1-0:{voltage}.7.0": ObisRule(f"L{phase} voltage", "decimal", "V"),
        f"1-0:{current}.7.0": ObisRule(f"L{phase} current", "decimal", "A"),
        f"1-0:{power_import}.7.0": ObisRule(
            f"L{phase} imported power", "decimal", "kW"
        ),
        f"1-0:{power_export}.7.0": ObisRule(
            f"L{phase} exported power", "decimal", "kW"
        ),
    }
    for phase, voltage, current, power_import, power_export in (
        (1, 32, 31, 21, 22),
        (2, 52, 51, 41, 42),
        (3, 72, 71, 61, 62),
    )
}


def calculate_crc(data: bytes) -> int:
    """Calculate the CRC-16/ARC used by DSMR telegrams."""
    crc = 0x0000
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def validate_crc(telegram: str) -> CrcResult:
    """Validate the CRC without normalising the telegram in any way."""
    match = _CRC.search(telegram)
    if match is None:
        return CrcResult(None, None, False, "missing or malformed CRC")
    try:
        payload = telegram[: match.start() + 1].encode("ascii")
    except UnicodeEncodeError:
        return CrcResult(match.group(1).upper(), None, False, "non-ASCII telegram")
    reported = match.group(1).upper()
    calculated = f"{calculate_crc(payload):04X}"
    return CrcResult(
        reported,
        calculated,
        reported == calculated,
        None if reported == calculated else "CRC mismatch",
    )


def required_obis_rules(phase_mode: str) -> dict[str, ObisRule]:
    """Return required continuous fields for the configured meter phases."""
    rules = {**_COMMON_RULES, **_PHASE_RULES[1]}
    if phase_mode == "three":
        rules.update(_PHASE_RULES[2])
        rules.update(_PHASE_RULES[3])
    return rules


def validate_required_obis(telegram: str, phase_mode: str) -> TelegramValidation:
    """Validate required OBIS lines in the current unmerged telegram."""
    raw_fields: dict[str, tuple[str, ...] | None] = {}
    for raw_line in telegram.splitlines():
        line = raw_line.strip()
        prefix = _OBIS_PREFIX.match(line)
        if prefix is None:
            continue
        identifier = prefix.group(1)
        match = _OBIS_LINE.fullmatch(line)
        raw_fields[identifier] = (
            tuple(_GROUP.findall(match.group("groups"))) if match is not None else None
        )

    missing: list[str] = []
    invalid: dict[str, str] = {}
    for identifier, rule in required_obis_rules(phase_mode).items():
        if identifier not in raw_fields:
            missing.append(identifier)
            continue
        groups = raw_fields[identifier]
        if groups is None:
            invalid[identifier] = "malformed OBIS line"
            continue
        error = _validate_groups(groups, rule)
        if error is not None:
            invalid[identifier] = error

    return TelegramValidation(tuple(missing), invalid)


def redact_equipment_ids(telegram: str) -> str:
    """Redact electricity and M-Bus equipment IDs before logging."""
    return _EQUIPMENT_ID.sub(r"\1(<redacted>)", telegram)


def _validate_groups(groups: tuple[str, ...], rule: ObisRule) -> str | None:
    """Return an explanation when a required field is invalid."""
    if len(groups) != 1:
        return f"expected one value group, received {len(groups)}"
    value = groups[0]
    if not value:
        return "empty value"

    if rule.kind == "text":
        return None
    if rule.kind == "timestamp":
        return None if _TIMESTAMP.fullmatch(value) else "invalid DSMR timestamp"
    if rule.kind == "version":
        return None if value.isdigit() and len(value) == 2 else "invalid DSMR version"

    number, separator, unit = value.rpartition("*")
    if not separator:
        number, unit = value, ""
    try:
        parsed = Decimal(number)
    except (InvalidOperation, ValueError):
        return "not numeric"
    if rule.unit is not None and unit.casefold() != rule.unit.casefold():
        return f"expected unit {rule.unit}, received {unit or 'none'}"
    if rule.kind == "integer" and parsed != parsed.to_integral_value():
        return "expected an integer"
    if rule.allowed is not None and int(parsed) not in rule.allowed:
        allowed = ", ".join(str(item) for item in sorted(rule.allowed))
        return f"expected one of {allowed}"
    return None

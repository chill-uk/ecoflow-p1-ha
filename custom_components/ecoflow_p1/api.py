"""Local API facade for the EcoFlow P1 Energy Tracker."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientSession

from .client import (
    EcoFlowP1Client,
    EcoFlowP1ConnectionError,
    EcoFlowP1ResponseError,
)
from .models import EcoFlowP1Data
from .parser import InvalidTelegramError, parse_telegram
from .validation import CrcResult, validate_crc


class EcoFlowP1Error(Exception):
    """Base exception for EcoFlow P1 communication errors."""


class EcoFlowP1TelegramError(EcoFlowP1ResponseError):
    """The EcoFlow P1 returned a telegram that failed integrity or parsing."""

    def __init__(self, message: str, telegram: str, crc: CrcResult) -> None:
        """Initialize an error containing data needed for safe debug logging."""
        super().__init__(message)
        self.telegram = telegram
        self.crc = crc


class EcoFlowP1Api:
    """Async facade combining raw HTTP transport and DSMR interpretation."""

    def __init__(self, session: ClientSession, host: str) -> None:
        """Initialize the API facade."""
        self._client = EcoFlowP1Client(session, host)

    @property
    def host(self) -> str:
        """Return the configured host."""
        return self._client.host

    async def async_get_data(self) -> EcoFlowP1Data:
        """Fetch and parse one response from /getdebugdata."""
        payload = await self._client.async_get_debug_payload()

        telegram_raw = payload.get("debugdata")
        if not isinstance(telegram_raw, str):
            raise EcoFlowP1ResponseError("JSON response has no debugdata telegram")

        crc = validate_crc(telegram_raw)
        if not crc.valid:
            raise EcoFlowP1TelegramError(
                crc.error or "Telegram CRC validation failed", telegram_raw, crc
            )

        try:
            telegram = parse_telegram(telegram_raw)
        except InvalidTelegramError as err:
            raise EcoFlowP1TelegramError(str(err), telegram_raw, crc) from err

        return EcoFlowP1Data(
            telegram=telegram,
            serial=_optional_string(payload.get("SN")),
            firmware_version=_optional_string(payload.get("VERSION_ALL")),
            timeout_times=_optional_int(payload.get("timeout_times")),
            crc_error_times=_optional_int(payload.get("crc_error_times")),
            total_times=_optional_int(payload.get("total_times")),
            raw_telegram=telegram_raw,
        )


def _optional_string(value: Any) -> str | None:
    """Return a trimmed non-empty string."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_int(value: Any) -> int | None:
    """Return an integer without allowing malformed metadata to fail an update."""
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# Re-export transport errors to preserve the integration's existing import surface.
__all__ = [
    "EcoFlowP1Api",
    "EcoFlowP1ConnectionError",
    "EcoFlowP1Error",
    "EcoFlowP1ResponseError",
    "EcoFlowP1TelegramError",
]

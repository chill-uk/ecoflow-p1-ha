"""Raw local HTTP transport for the EcoFlow P1 Energy Tracker."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import API_PATH, REQUEST_TIMEOUT


class EcoFlowP1TransportError(Exception):
    """Base exception for local transport failures."""


class EcoFlowP1TransportConnectionError(EcoFlowP1TransportError):
    """The EcoFlow P1 could not be reached."""


class EcoFlowP1TransportResponseError(EcoFlowP1TransportError):
    """The EcoFlow P1 returned an invalid HTTP/JSON response."""


class EcoFlowP1Client:
    """Fetch raw local data without interpreting DSMR content."""

    def __init__(self, session: ClientSession, host: str) -> None:
        self._session = session
        self._host = host

    @property
    def host(self) -> str:
        """Return the configured host."""
        return self._host

    async def async_get_debug_payload(self) -> Mapping[str, Any]:
        """Fetch one raw /getdebugdata payload."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(
                    f"http://{self._host}{API_PATH}", allow_redirects=False
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
        except TimeoutError as err:
            raise EcoFlowP1TransportConnectionError(
                f"Request to {API_PATH} timed out after {REQUEST_TIMEOUT} seconds"
            ) from err
        except ClientError as err:
            detail = str(err).strip() or type(err).__name__
            raise EcoFlowP1TransportConnectionError(
                f"Request to {API_PATH} failed: {detail}"
            ) from err
        except ValueError as err:
            raise EcoFlowP1TransportResponseError(\n                "Device returned invalid JSON"\n            ) from err

        if not isinstance(payload, Mapping):
            raise EcoFlowP1TransportResponseError("JSON response is not an object")
        return payload

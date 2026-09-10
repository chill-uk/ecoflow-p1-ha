"""Tests for the local EcoFlow HTTP API client."""

from __future__ import annotations

import sys
import types
import unittest

from aiohttp import ClientError

from .helpers import load_module
from .test_parser import TELEGRAM

load_module("custom_components.ecoflow_p1.models")
load_module("custom_components.ecoflow_p1.parser")
constants = types.ModuleType("custom_components.ecoflow_p1.const")
constants.API_PATH = "/getdebugdata"
constants.REQUEST_TIMEOUT = 4
sys.modules[constants.__name__] = constants
api_module = load_module("custom_components.ecoflow_p1.api")


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(self, payload=None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error

    async def json(self, content_type=None):
        if self.error and isinstance(self.error, ValueError):
            raise self.error
        return self.payload


class FakeSession:
    """Record a request and return a prepared response."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.url = None
        self.allow_redirects = None

    def get(self, url: str, *, allow_redirects: bool):
        self.url = url
        self.allow_redirects = allow_redirects
        return self.response


class ApiTests(unittest.IsolatedAsyncioTestCase):
    """Verify endpoint, response validation, and tolerant metadata parsing."""

    async def test_fetches_local_endpoint_and_parses_payload(self) -> None:
        """Return a complete typed response from valid JSON."""
        session = FakeSession(
            FakeResponse(
                {
                    "debugdata": TELEGRAM,
                    "SN": " P1-123 ",
                    "VERSION_ALL": "1.1.07",
                    "timeout_times": 12,
                    "crc_error_times": "2",
                    "total_times": 99,
                }
            )
        )
        client = api_module.EcoFlowP1Api(session, "p1.local")

        data = await client.async_get_data()

        self.assertEqual(session.url, "http://p1.local/getdebugdata")
        self.assertFalse(session.allow_redirects)
        self.assertEqual(data.serial, "P1-123")
        self.assertEqual(data.firmware_version, "1.1.07")
        self.assertEqual(data.crc_error_times, 2)

    async def test_invalid_json_is_a_response_error(self) -> None:
        """Distinguish invalid JSON from a network failure."""
        client = api_module.EcoFlowP1Api(
            FakeSession(FakeResponse(error=ValueError("bad json"))), "p1.local"
        )
        with self.assertRaises(api_module.EcoFlowP1ResponseError):
            await client.async_get_data()

    async def test_missing_or_invalid_telegram_is_a_response_error(self) -> None:
        """Require debugdata containing a genuine DSMR telegram."""
        for payload in ({}, {"debugdata": "not DSMR"}):
            with self.subTest(payload=payload):
                client = api_module.EcoFlowP1Api(
                    FakeSession(FakeResponse(payload)), "p1.local"
                )
                with self.assertRaises(api_module.EcoFlowP1ResponseError):
                    await client.async_get_data()

    async def test_http_client_failure_is_a_connection_error(self) -> None:
        """Map temporary aiohttp failures to the retryable API error."""
        client = api_module.EcoFlowP1Api(
            FakeSession(FakeResponse(error=ClientError("offline"))), "p1.local"
        )
        with self.assertRaises(api_module.EcoFlowP1ConnectionError) as raised:
            await client.async_get_data()

        self.assertEqual(
            str(raised.exception), "Request to /getdebugdata failed: offline"
        )

    async def test_timeout_has_a_descriptive_connection_error(self) -> None:
        """Do not produce a blank coordinator message when a request times out."""
        client = api_module.EcoFlowP1Api(
            FakeSession(FakeResponse(error=TimeoutError())), "p1.local"
        )

        with self.assertRaises(api_module.EcoFlowP1ConnectionError) as raised:
            await client.async_get_data()

        self.assertEqual(
            str(raised.exception),
            "Request to /getdebugdata timed out after 4 seconds",
        )

    async def test_empty_client_error_uses_exception_name(self) -> None:
        """Keep an aiohttp failure useful even when its message is empty."""
        client = api_module.EcoFlowP1Api(
            FakeSession(FakeResponse(error=ClientError())), "p1.local"
        )

        with self.assertRaises(api_module.EcoFlowP1ConnectionError) as raised:
            await client.async_get_data()

        self.assertEqual(
            str(raised.exception),
            "Request to /getdebugdata failed: ClientError",
        )

    async def test_rejects_a_crc_mismatch(self) -> None:
        """Do not publish a telegram whose contents fail their reported CRC."""
        invalid = TELEGRAM.replace("00.123*kW", "00.124*kW")
        client = api_module.EcoFlowP1Api(
            FakeSession(FakeResponse({"debugdata": invalid})), "p1.local"
        )

        with self.assertRaises(api_module.EcoFlowP1TelegramError) as raised:
            await client.async_get_data()

        self.assertEqual(raised.exception.crc.reported, "6A72")
        self.assertFalse(raised.exception.crc.valid)


if __name__ == "__main__":
    unittest.main()

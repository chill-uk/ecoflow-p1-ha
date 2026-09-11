"""Tests for encrypted diagnostic capture."""

from __future__ import annotations

import base64
import json
import unittest
from datetime import UTC, datetime

from nacl.public import PrivateKey, SealedBox

from .helpers import load_module

capture_module = load_module("custom_components.ecoflow_p1.capture")


class EncryptedDiagnosticCaptureTests(unittest.TestCase):
    """Verify immediate encryption and bounded in-memory retention."""

    def setUp(self) -> None:
        """Create an isolated support key pair."""
        self.private_key = PrivateKey.generate()
        self.public_key = base64.b64encode(bytes(self.private_key.public_key)).decode()

    def test_embedded_support_public_key_accepts_records(self) -> None:
        capture = capture_module.EncryptedDiagnosticCapture(True)

        capture.capture({"telegram": "secret"})

        self.assertEqual(capture.diagnostics()["records_captured"], 1)

    def test_round_trip_contains_context_but_export_has_no_plaintext(self) -> None:
        telegram = "/ISK5\\2M550E-1011\r\n0-0:96.1.1(SECRET-METER-SERIAL)\r\n!0000\r\n"
        capture = capture_module.EncryptedDiagnosticCapture(
            True, public_key=self.public_key, key_id="test-key"
        )

        capture.capture(
            {
                "outcome": "crc_invalid",
                "phase_mode": "single",
                "telegram": telegram,
                "crc": {"valid": False},
            }
        )
        diagnostics = capture.diagnostics()
        exported = json.dumps(diagnostics)

        self.assertEqual(diagnostics["records_captured"], 1)
        self.assertNotIn(telegram, exported)
        self.assertNotIn("SECRET-METER-SERIAL", exported)

        ciphertext = base64.b64decode(diagnostics["encrypted_records"][0])
        plaintext = SealedBox(self.private_key).decrypt(ciphertext)
        record = json.loads(plaintext)
        self.assertEqual(record["telegram"], telegram)
        self.assertEqual(record["outcome"], "crc_invalid")
        self.assertEqual(record["phase_mode"], "single")

    def test_disabled_capture_does_not_validate_or_store_a_key(self) -> None:
        capture = capture_module.EncryptedDiagnosticCapture(
            False, public_key="not-a-key"
        )

        capture.capture({"telegram": "secret"})

        self.assertEqual(capture.diagnostics()["records_captured"], 0)
        self.assertEqual(capture.diagnostics()["status"], "disabled")

    def test_stops_at_record_limit(self) -> None:
        capture = capture_module.EncryptedDiagnosticCapture(
            True, public_key=self.public_key
        )

        for index in range(capture_module.CAPTURE_MAX_RECORDS + 1):
            capture.capture({"sequence": index})

        diagnostics = capture.diagnostics()
        self.assertEqual(
            diagnostics["records_captured"], capture_module.CAPTURE_MAX_RECORDS
        )
        self.assertEqual(diagnostics["status"], "complete")
        self.assertEqual(diagnostics["stop_reason"], "record_limit")

    def test_stops_at_duration_limit(self) -> None:
        monotonic_time = [100.0]
        capture = capture_module.EncryptedDiagnosticCapture(
            True,
            public_key=self.public_key,
            now=lambda: datetime(2026, 9, 11, tzinfo=UTC),
            monotonic=lambda: monotonic_time[0],
        )
        capture.capture({"sequence": 1})
        monotonic_time[0] += capture_module.CAPTURE_DURATION_SECONDS

        capture.capture({"sequence": 2})

        diagnostics = capture.diagnostics()
        self.assertEqual(diagnostics["records_captured"], 1)
        self.assertEqual(diagnostics["status"], "complete")
        self.assertEqual(diagnostics["stop_reason"], "duration_limit")


if __name__ == "__main__":
    unittest.main()

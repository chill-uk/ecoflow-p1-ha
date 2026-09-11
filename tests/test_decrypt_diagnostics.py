"""Tests for the support diagnostics decryption utility."""

from __future__ import annotations

import base64
import importlib.util
import unittest

from nacl.public import PrivateKey

from .helpers import ROOT, load_module

capture_module = load_module("custom_components.ecoflow_p1.capture")

_SCRIPT = ROOT / "scripts" / "decrypt_diagnostics.py"
_SPEC = importlib.util.spec_from_file_location("decrypt_diagnostics", _SCRIPT)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Cannot load {_SCRIPT}")
decrypt_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(decrypt_module)


class DecryptDiagnosticsTests(unittest.TestCase):
    """Verify Home Assistant diagnostics files can be decrypted."""

    def test_decrypts_home_assistant_wrapped_diagnostics(self) -> None:
        private_key = PrivateKey.generate()
        public_key = base64.b64encode(bytes(private_key.public_key)).decode()
        private_key_text = base64.b64encode(bytes(private_key)).decode()
        capture = capture_module.EncryptedDiagnosticCapture(
            True, public_key=public_key
        )
        capture.capture({"outcome": "accepted", "telegram": "secret telegram"})
        capture_data = capture.diagnostics()
        encrypted_records = capture_data.pop("encrypted_records")
        diagnostics = {
            "home_assistant": {"installation_type": "Home Assistant OS"},
            "data": {
                "schema_version": 1,
                "integration_version": "0.2.7-beta.1",
                "home_assistant_version": "2026.9.0",
                "firmware_version": "1.1.07",
                "phase_mode": "single",
                "capture": capture_data,
                "encrypted_records": encrypted_records,
            },
        }

        result = decrypt_module.decrypt_diagnostics(diagnostics, private_key_text)

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["decrypted_records"][0]["telegram"], "secret telegram")

    def test_rejects_diagnostics_without_records(self) -> None:
        with self.assertRaisesRegex(ValueError, "No encrypted records found"):
            decrypt_module.decrypt_diagnostics({"data": {}}, "unused")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Decrypt EcoFlow P1 diagnostic records with the support private key."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from nacl.exceptions import CryptoError
from nacl.public import PrivateKey, SealedBox


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decrypt an EcoFlow P1 Home Assistant diagnostics download."
    )
    parser.add_argument("diagnostics", type=Path, help="Downloaded diagnostics JSON")
    parser.add_argument("private_key", type=Path, help="Base64 private key file")
    return parser.parse_args()


def decrypt_diagnostics(
    diagnostics: dict[str, Any], private_key_text: str
) -> dict[str, Any]:
    """Return metadata and decrypted records."""
    try:
        private_key = PrivateKey(
            base64.b64decode(private_key_text.strip(), validate=True)
        )
    except (ValueError, TypeError) as err:
        raise ValueError("Private key is not valid Base64") from err

    box = SealedBox(private_key)
    records = []
    for index, encoded in enumerate(diagnostics.get("encrypted_records", []), start=1):
        try:
            ciphertext = base64.b64decode(encoded, validate=True)
            records.append(json.loads(box.decrypt(ciphertext)))
        except (ValueError, TypeError, CryptoError, json.JSONDecodeError) as err:
            raise ValueError(f"Could not decrypt record {index}") from err

    return {
        "schema_version": diagnostics.get("schema_version"),
        "integration_version": diagnostics.get("integration_version"),
        "home_assistant_version": diagnostics.get("home_assistant_version"),
        "firmware_version": diagnostics.get("firmware_version"),
        "phase_mode": diagnostics.get("phase_mode"),
        "capture": diagnostics.get("capture"),
        "decrypted_records": records,
    }


def main() -> None:
    """Decrypt a diagnostics file and write readable JSON to standard output."""
    args = _arguments()
    diagnostics = json.loads(args.diagnostics.read_text(encoding="utf-8"))
    private_key_text = args.private_key.read_text(encoding="ascii")
    print(json.dumps(decrypt_diagnostics(diagnostics, private_key_text), indent=2))


if __name__ == "__main__":
    main()

"""Encrypted, bounded DSMR capture for support diagnostics."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Final

from nacl.public import PublicKey, SealedBox

CAPTURE_DURATION_SECONDS: Final = 10 * 60
CAPTURE_MAX_RECORDS: Final = 120
SUPPORT_KEY_ID: Final = "support-2026-01"
SUPPORT_PUBLIC_KEY: Final = "YcKfN202beTpo3uLz7mXrnKUqH93dLQTS4YL/QmQZy8="


class EncryptedDiagnosticCapture:
    """Encrypt diagnostic records immediately and retain ciphertext only."""

    def __init__(
        self,
        enabled: bool,
        *,
        public_key: str = SUPPORT_PUBLIC_KEY,
        key_id: str = SUPPORT_KEY_ID,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        """Initialize a bounded capture session."""
        self.enabled = enabled
        self.key_id = key_id
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.monotonic
        self._box = (
            SealedBox(PublicKey(base64.b64decode(public_key, validate=True)))
            if enabled
            else None
        )
        self._started_at = self._now() if enabled else None
        self._started_monotonic = self._monotonic() if enabled else None
        self._stopped_at: datetime | None = None
        self._stop_reason: str | None = None
        self._encrypted_records: list[str] = []

    @property
    def active(self) -> bool:
        """Return whether capture can accept another record."""
        if not self.enabled or self._stop_reason is not None:
            return False
        if len(self._encrypted_records) >= CAPTURE_MAX_RECORDS:
            self._stop("record_limit")
            return False
        if (
            self._started_monotonic is not None
            and self._monotonic() - self._started_monotonic
            >= CAPTURE_DURATION_SECONDS
        ):
            self._stop("duration_limit")
            return False
        return True

    def capture(self, record: Mapping[str, Any]) -> None:
        """Encrypt and retain one JSON record without retaining its plaintext."""
        if not self.active or self._box is None:
            return

        payload = {
            "captured_at": self._now().isoformat(),
            **record,
        }
        plaintext = json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
        ciphertext = self._box.encrypt(plaintext)
        self._encrypted_records.append(base64.b64encode(ciphertext).decode("ascii"))

        if len(self._encrypted_records) >= CAPTURE_MAX_RECORDS:
            self._stop("record_limit")

    def diagnostics(self) -> dict[str, Any]:
        """Return safe capture metadata and encrypted records."""
        active = self.active
        if not self.enabled:
            status = "disabled"
        elif active:
            status = "active"
        else:
            status = "complete"

        return {
            "enabled": self.enabled,
            "status": status,
            "key_id": self.key_id,
            "algorithm": "libsodium_sealed_box_curve25519xsalsa20poly1305",
            "started_at": (
                self._started_at.isoformat() if self._started_at is not None else None
            ),
            "stopped_at": (
                self._stopped_at.isoformat() if self._stopped_at is not None else None
            ),
            "stop_reason": self._stop_reason,
            "duration_limit_seconds": CAPTURE_DURATION_SECONDS,
            "record_limit": CAPTURE_MAX_RECORDS,
            "records_captured": len(self._encrypted_records),
            "encrypted_records": list(self._encrypted_records),
        }

    def clear(self) -> None:
        """Discard all encrypted records."""
        self._encrypted_records.clear()
        self.enabled = False
        self._box = None
        self._stop_reason = "cleared"
        self._stopped_at = self._now()

    def _stop(self, reason: str) -> None:
        """Mark the capture complete."""
        if self._stop_reason is None:
            self._stop_reason = reason
            self._stopped_at = self._now()

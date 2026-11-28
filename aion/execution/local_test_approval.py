"""Test-only HMAC approval provider with a separate SQLite one-time-token store.

This module is deliberately not a production approval integration. The HMAC key
is generated in memory for each provider instance and is never persisted.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from aion.execution.channel import ConfirmationEvent, hash_payload


class ApprovalError(ValueError):
    """A fail-closed approval verification or consumption failure."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ApprovalReceipt:
    """HMAC-authenticated test receipt bound to one AION confirmation event."""

    request_id: str
    confirmation_event_id: str
    action: str
    tool: str
    session_id: str
    payload_hash: str
    target_ref: str
    expected_generation: int
    expected_version: int
    target_hash: str
    jti: str
    issued_at: int
    expires_at: int
    signature: str

    def signed_claims(self) -> dict[str, Any]:
        """Return the canonical claim names covered by the HMAC signature."""
        return {
            "aion.confirmation_event_id": self.confirmation_event_id,
            "action": self.action,
            "expected_generation": self.expected_generation,
            "expected_version": self.expected_version,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "jti": self.jti,
            "payload_hash": self.payload_hash,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "target_hash": self.target_hash,
            "target_ref": self.target_ref,
            "tool": self.tool,
        }


class LocalTestApprovalProvider:
    """Issue and consume local test receipts; refuses to run outside test mode."""

    def __init__(
        self,
        jti_store_path: str | os.PathLike[str] = ":memory:",
        *,
        ttl_seconds: int = 120,
    ) -> None:
        self._require_test_environment()
        if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        self.ttl_seconds = ttl_seconds
        raw_store_path = os.fspath(jti_store_path)
        self.store_path = (
            raw_store_path
            if raw_store_path == ":memory:"
            else str(Path(raw_store_path).expanduser().resolve(strict=False))
        )
        self.store_identity: str | tuple[int, int] | None = (
            ":memory:" if self.store_path == ":memory:" else None
        )
        self._key = secrets.token_bytes(32)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.store_path,
            timeout=10,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.execute("PRAGMA busy_timeout = 10000")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS issued_jti (
                jti TEXT PRIMARY KEY,
                request_id TEXT NOT NULL UNIQUE,
                consumed INTEGER NOT NULL DEFAULT 0 CHECK (consumed IN (0, 1)),
                expires_at INTEGER NOT NULL
            )"""
        )
        if self.store_path != ":memory:":
            file_stat = os.stat(self.store_path)
            self.store_identity = file_stat.st_dev, file_stat.st_ino

    @staticmethod
    def _require_test_environment() -> None:
        if os.environ.get("AION_ENV") != "test":
            raise RuntimeError(
                "LocalTestApprovalProvider is available only when AION_ENV=test"
            )

    @staticmethod
    def _path_identity(path: str) -> str:
        if path == ":memory:":
            return path
        return str(Path(path).expanduser().resolve())

    @staticmethod
    def _canonical_bytes(claims: dict[str, Any]) -> bytes:
        return json.dumps(
            claims,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    def _sign(self, claims: dict[str, Any]) -> str:
        return hmac.new(
            self._key, self._canonical_bytes(claims), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def _event_claims(
        event: ConfirmationEvent,
        payload: Any,
        *,
        jti: str,
        issued_at: int,
        expires_at: int,
    ) -> ApprovalReceipt:
        if not isinstance(event, ConfirmationEvent):
            raise ApprovalError("unissued_confirmation")
        digest = hash_payload(payload)
        if event.payload_hash != digest:
            raise ApprovalError("payload_mismatch")
        if not event.request_id:
            raise ApprovalError("request_id_missing")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                event.action,
                event.tool,
                event.session_id,
                event.target_ref,
                event.target_version,
                event.target_hash,
            )
        ):
            raise ApprovalError("target_binding_incomplete")
        if (
            not isinstance(event.expected_generation, int)
            or isinstance(event.expected_generation, bool)
            or event.expected_generation <= 0
        ):
            raise ApprovalError("expected_generation_missing")
        try:
            expected_version = int(event.target_version)
        except (TypeError, ValueError) as exc:
            raise ApprovalError("expected_version_invalid") from exc
        if expected_version <= 0 or str(expected_version) != event.target_version:
            raise ApprovalError("expected_version_invalid")
        return ApprovalReceipt(
            request_id=event.request_id,
            confirmation_event_id=event.request_id,
            action=event.action,
            tool=event.tool,
            session_id=event.session_id,
            payload_hash=digest,
            target_ref=event.target_ref,
            expected_generation=event.expected_generation,
            expected_version=expected_version,
            target_hash=event.target_hash,
            jti=jti,
            issued_at=issued_at,
            expires_at=expires_at,
            signature="",
        )

    def issue_test_approval(
        self, event: ConfirmationEvent, payload: Any
    ) -> ApprovalReceipt:
        """Create a test receipt for one event; this method simulates approval."""
        self._require_test_environment()
        if not isinstance(event, ConfirmationEvent):
            raise ApprovalError("unissued_confirmation")
        now = int(time.time())
        if event.expires_at.timestamp() <= now:
            raise ApprovalError("expired")
        expires_at = min(int(event.expires_at.timestamp()), now + self.ttl_seconds)
        if expires_at <= now:
            raise ApprovalError("expired")
        jti = secrets.token_urlsafe(24)
        unsigned = self._event_claims(
            event,
            payload,
            jti=jti,
            issued_at=now,
            expires_at=expires_at,
        )
        receipt = replace(unsigned, signature=self._sign(unsigned.signed_claims()))
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    "INSERT INTO issued_jti(jti, request_id, consumed, expires_at) "
                    "VALUES (?, ?, 0, ?)",
                    (receipt.jti, receipt.request_id, receipt.expires_at),
                )
                self._connection.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                self._rollback()
                raise ApprovalError("approval_already_issued") from exc
            except sqlite3.Error as exc:
                self._rollback()
                raise ApprovalError("external_approval_unavailable") from exc
        return receipt

    def validate_signature(
        self,
        receipt: ApprovalReceipt,
        event: ConfirmationEvent,
        payload: Any,
        *,
        allow_expired: bool = False,
    ) -> None:
        """Verify signature and all event claims without consuming the jti."""
        self._require_test_environment()
        if not isinstance(receipt, ApprovalReceipt):
            raise ApprovalError("approval_receipt_invalid")
        if not isinstance(event, ConfirmationEvent):
            raise ApprovalError("unissued_confirmation")
        try:
            expected_signature = self._sign(receipt.signed_claims())
        except (TypeError, ValueError):
            raise ApprovalError("approval_receipt_invalid") from None
        if not isinstance(receipt.signature, str) or not hmac.compare_digest(
            receipt.signature, expected_signature
        ):
            raise ApprovalError("approval_signature_invalid")
        try:
            expected_version = int(event.target_version or "")
            digest = hash_payload(payload)
        except (TypeError, ValueError):
            raise ApprovalError("approval_claim_mismatch") from None
        event_expires_at = int(event.expires_at.timestamp())
        matching = (
            receipt.request_id == event.request_id
            and receipt.confirmation_event_id == event.request_id
            and receipt.action == event.action
            and receipt.tool == event.tool
            and receipt.session_id == event.session_id
            and receipt.payload_hash == digest == event.payload_hash
            and receipt.target_ref == event.target_ref
            and receipt.expected_generation == event.expected_generation
            and receipt.expected_version == expected_version
            and str(expected_version) == event.target_version
            and receipt.target_hash == event.target_hash
            and receipt.expires_at <= event_expires_at
            and receipt.issued_at <= receipt.expires_at
            and bool(receipt.jti)
        )
        if not matching:
            raise ApprovalError("approval_claim_mismatch")
        now = int(time.time())
        if not allow_expired and (
            now >= receipt.expires_at or now >= event_expires_at
        ):
            raise ApprovalError("approval_expired")

    def is_jti_unused(self, receipt: ApprovalReceipt) -> bool:
        """Check the separate approval ledger; callers still consume atomically."""
        self._require_test_environment()
        with self._lock:
            row = self._connection.execute(
                "SELECT request_id, consumed FROM issued_jti WHERE jti = ?",
                (receipt.jti,),
            ).fetchone()
        if row is None or row[0] != receipt.request_id:
            raise ApprovalError("approval_jti_unknown")
        if row[1] != 0:
            raise ApprovalError("approval_replayed")
        return True

    def consume(
        self,
        receipt: ApprovalReceipt,
        event: ConfirmationEvent,
        payload: Any,
    ) -> None:
        """Atomically consume a verified jti in the separate approval database."""
        self._require_test_environment()
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self.validate_signature(receipt, event, payload)
                row = self._connection.execute(
                    "SELECT request_id, consumed FROM issued_jti WHERE jti = ?",
                    (receipt.jti,),
                ).fetchone()
                if row is None or row[0] != receipt.request_id:
                    self._rollback()
                    raise ApprovalError("approval_jti_unknown")
                if row[1] != 0:
                    self._rollback()
                    raise ApprovalError("approval_replayed")
                updated = self._connection.execute(
                    "UPDATE issued_jti SET consumed = 1 "
                    "WHERE jti = ? AND request_id = ? AND consumed = 0",
                    (receipt.jti, receipt.request_id),
                ).rowcount
                if updated != 1:
                    self._rollback()
                    raise ApprovalError("approval_replayed")
                self._connection.execute("COMMIT")
            except ApprovalError:
                self._rollback()
                raise
            except sqlite3.Error as exc:
                self._rollback()
                raise ApprovalError("external_approval_unavailable") from exc

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            self._connection.execute("ROLLBACK")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

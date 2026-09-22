"""Confirmation channel for AION execution boundary."""
from __future__ import annotations

import copy
import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

_AUDIT_GENESIS_HASH = "0" * 64


def hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hash_audit_record(record: dict[str, Any]) -> str:
    content = {
        key: value
        for key, value in record.items()
        if key != "record_hash"
    }
    canonical = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConfirmationEvent:
    request_id: str
    action: str
    tool: str
    session_id: str
    nonce: str
    issued_at: datetime
    expires_at: datetime
    payload_hash: str | None = None
    target_version: str | None = None
    target_hash: str | None = None
    used: bool = False

    def is_valid_for(
        self,
        action: str,
        tool: str,
        session_id: str,
        now: datetime,
        payload_hash: str | None = None,
        current_target_version: str | None = None,
        current_target_hash: str | None = None,
        request_id: str | None = None,
    ) -> tuple[bool, str]:
        if self.used:
            return False, "already_used"
        if now > self.expires_at:
            return False, "expired"
        if request_id is not None and request_id != self.request_id:
            return False, "request_id_mismatch"
        if action != self.action:
            return False, "action_mismatch"
        if tool != self.tool:
            return False, "tool_mismatch"
        if session_id != self.session_id:
            return False, "session_mismatch"
        if (
            self.payload_hash is not None
            and payload_hash is not None
            and payload_hash != self.payload_hash
        ):
            return False, "payload_mismatch"
        if (
            self.target_version is not None
            and current_target_version is not None
            and current_target_version != self.target_version
        ):
            return False, "target_drift"
        if (
            self.target_hash is not None
            and current_target_hash is not None
            and current_target_hash != self.target_hash
        ):
            return False, "target_hash_mismatch"
        return True, "ok"


class ConfirmationChannel:
    def __init__(self, ttl_seconds: int = 300):
        if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        self.ttl = timedelta(seconds=ttl_seconds)
        self._events: dict[str, ConfirmationEvent] = {}
        self._audit: list[dict[str, Any]] = []
        self._consume_lock = threading.Lock()
        self._audit_lock = threading.Lock()

    def _append_audit(self, record: dict[str, Any]) -> None:
        with self._audit_lock:
            previous_hash = (
                self._audit[-1]["record_hash"]
                if self._audit
                else _AUDIT_GENESIS_HASH
            )
            chained_record = dict(record)
            chained_record["prev_hash"] = previous_hash
            chained_record["record_hash"] = _hash_audit_record(chained_record)
            self._audit.append(chained_record)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def issue(
        self,
        action: str,
        tool: str,
        session_id: str,
        payload: Any | None = None,
        payload_hash: str | None = None,
        target_version: str | None = None,
        target_hash: str | None = None,
    ) -> ConfirmationEvent:
        if payload is not None and payload_hash is None:
            payload_hash = hash_payload(payload)
        now = self._now()
        event = ConfirmationEvent(
            request_id=str(uuid4()),
            action=action,
            tool=tool,
            session_id=session_id,
            nonce=str(uuid4()),
            issued_at=now,
            expires_at=now + self.ttl,
            payload_hash=payload_hash,
            target_version=target_version,
            target_hash=target_hash,
        )
        self._events[event.request_id] = event
        self._append_audit({
            "event": "issued",
            "request_id": event.request_id,
            "action": action,
            "tool": tool,
            "session_id": session_id,
            "timestamp": now.isoformat(),
        })
        return event

    def verify(
        self,
        event: ConfirmationEvent,
        action: str,
        tool: str,
        session_id: str,
        payload: Any | None = None,
        payload_hash: str | None = None,
        current_target_version: str | None = None,
        current_target_hash: str | None = None,
        request_id: str | None = None,
    ) -> tuple[bool, str]:
        if payload is not None and payload_hash is None:
            payload_hash = hash_payload(payload)
        now = self._now()
        valid, reason = event.is_valid_for(
            action=action,
            tool=tool,
            session_id=session_id,
            now=now,
            payload_hash=payload_hash,
            current_target_version=current_target_version,
            current_target_hash=current_target_hash,
            request_id=request_id,
        )
        self._append_audit({
            "event": "verified",
            "request_id": event.request_id,
            "result": "allowed" if valid else "refused",
            "reason": reason,
            "timestamp": now.isoformat(),
        })
        return valid, reason

    def consume(self, event: ConfirmationEvent) -> None:
        """Mark event as used. Caller must verify first.

        WARNING: this does not verify. Use verify_and_consume()
        for the safe path.
        """
        if event.used:
            raise ValueError("Event already consumed")
        object.__setattr__(event, "used", True)
        self._append_audit({
            "event": "consumed",
            "request_id": event.request_id,
            "timestamp": self._now().isoformat(),
        })

    def verify_and_consume(
        self,
        event: ConfirmationEvent,
        action: str,
        tool: str,
        session_id: str,
        payload: Any | None = None,
        payload_hash: str | None = None,
        current_target_version: str | None = None,
        current_target_hash: str | None = None,
        request_id: str | None = None,
    ) -> tuple[bool, str]:
        """Verify scope, then consume only if valid.

        This is the safe path. Use it unless you have a specific
        reason to separate verify from consume.
        """
        with self._consume_lock:
            valid, reason = self.verify(
                event=event,
                action=action,
                tool=tool,
                session_id=session_id,
                payload=payload,
                payload_hash=payload_hash,
                current_target_version=current_target_version,
                current_target_hash=current_target_hash,
                request_id=request_id,
            )
            if valid:
                object.__setattr__(event, "used", True)
                self._append_audit({
                    "event": "consumed",
                    "request_id": event.request_id,
                    "timestamp": self._now().isoformat(),
                })
            return valid, reason

    def audit_log(self) -> list[dict[str, Any]]:
        with self._audit_lock:
            return copy.deepcopy(self._audit)

    def verify_audit_integrity(self) -> tuple[bool, int | None]:
        with self._audit_lock:
            expected_previous_hash = _AUDIT_GENESIS_HASH
            for index, record in enumerate(self._audit):
                if record.get("prev_hash") != expected_previous_hash:
                    return False, index

                expected_record_hash = _hash_audit_record(record)
                if record.get("record_hash") != expected_record_hash:
                    return False, index

                expected_previous_hash = record["record_hash"]

            return True, None

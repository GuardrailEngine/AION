"""Confirmation channel for AION execution boundary.

Events issued by this channel are scoped capabilities, not proof of external
user approval. The execution boundary fails closed until a trusted approval
verifier is integrated.
"""
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


def _hash_target_ref(target_ref: str | None) -> str | None:
    if target_ref is None:
        return None
    return hashlib.sha256(target_ref.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConfirmationEvent:
    """Channel-issued scope for a requested action; not an approval receipt."""

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
    target_ref: str | None = None
    expected_generation: int | None = None
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
        current_target_ref: str | None = None,
        current_expected_generation: int | None = None,
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
        if self.payload_hash is None or payload_hash is None:
            return False, "payload_binding_missing"
        if payload_hash != self.payload_hash:
            return False, "payload_mismatch"

        target_values = (
            self.target_ref,
            self.target_version,
            self.target_hash,
        )
        target_is_bound = any(value is not None for value in target_values) or (
            self.expected_generation is not None
        )
        if target_is_bound:
            if not all(
                isinstance(value, str) and value.strip()
                for value in target_values
            ):
                return False, "target_binding_incomplete"
            if (
                current_target_ref is None
                or current_target_version is None
                or current_target_hash is None
            ):
                return False, "target_state_unavailable"
            if current_target_ref != self.target_ref:
                return False, "target_ref_mismatch"
            if current_target_version != self.target_version:
                return False, "target_drift"
            if current_target_hash != self.target_hash:
                return False, "target_hash_mismatch"
            if self.expected_generation is not None:
                if (
                    not isinstance(self.expected_generation, int)
                    or isinstance(self.expected_generation, bool)
                    or self.expected_generation <= 0
                ):
                    return False, "target_generation_invalid"
                if current_expected_generation is None:
                    return False, "target_state_unavailable"
                if current_expected_generation != self.expected_generation:
                    return False, "target_generation_mismatch"
            elif current_expected_generation is not None:
                return False, "target_binding_mismatch"
        elif any(
            value is not None
            for value in (
                current_target_ref,
                current_target_version,
                current_target_hash,
                current_expected_generation,
            )
        ):
            return False, "target_binding_mismatch"

        return True, "ok"


class ConfirmationChannel:
    """Issue scoped event objects and consume them atomically once.

    Issuance and scope validation do not prove that an external user approved
    the action. Callers must not treat a successful verification here as that
    proof; ExecutionBoundary deliberately refuses dispatch without a trusted
    approval integration.
    """

    def __init__(self, ttl_seconds: int = 300):
        if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        self.ttl = timedelta(seconds=ttl_seconds)
        self._events: dict[str, ConfirmationEvent] = {}
        self._consumed_ids: set[str] = set()
        self._audit: list[dict[str, Any]] = []
        self._consume_lock = threading.RLock()
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

    def _owns_event(self, event: Any) -> bool:
        if not isinstance(event, ConfirmationEvent):
            return False
        with self._consume_lock:
            return self._events.get(event.request_id) is event

    def _is_consumed(self, event: Any) -> bool:
        if not isinstance(event, ConfirmationEvent):
            return False
        with self._consume_lock:
            return event.request_id in self._consumed_ids

    def issue(
        self,
        action: str,
        tool: str,
        session_id: str,
        payload: Any | None = None,
        payload_hash: str | None = None,
        target_version: str | None = None,
        target_hash: str | None = None,
        target_ref: str | None = None,
        expected_generation: int | None = None,
    ) -> ConfirmationEvent:
        if payload_hash is None:
            payload_hash = hash_payload(payload)
        elif not isinstance(payload_hash, str) or not payload_hash:
            raise ValueError("payload_hash must be a non-empty string")
        elif payload_hash != hash_payload(payload):
            raise ValueError("payload_hash does not match payload")

        target_values = (target_ref, target_version, target_hash)
        if any(value is not None for value in target_values) and not all(
            isinstance(value, str) and value.strip()
            for value in target_values
        ):
            raise ValueError(
                "target_ref, target_version, and target_hash must be bound together"
            )
        if expected_generation is not None and (
            not isinstance(expected_generation, int)
            or isinstance(expected_generation, bool)
            or expected_generation <= 0
            or not all(value is not None for value in target_values)
        ):
            raise ValueError(
                "expected_generation must be positive and accompany a target binding"
            )

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
            target_ref=target_ref,
            expected_generation=expected_generation,
        )
        with self._consume_lock:
            self._events[event.request_id] = event
            self._append_audit({
                "event": "issued",
                "request_id": event.request_id,
                "action": action,
                "tool": tool,
                "session_id": session_id,
                "payload_hash": payload_hash,
                "target_ref_hash": _hash_target_ref(target_ref),
                "target_version": target_version,
                "target_hash": target_hash,
                "expected_generation": expected_generation,
                "timestamp": now.isoformat(),
            })
        return event

    def _verify_unlocked(
        self,
        event: ConfirmationEvent,
        action: str,
        tool: str,
        session_id: str,
        payload: Any | None,
        payload_hash: str | None,
        current_target_version: str | None,
        current_target_hash: str | None,
        request_id: str | None,
        current_target_ref: str | None,
        current_expected_generation: int | None,
    ) -> tuple[bool, str]:
        if not isinstance(event, ConfirmationEvent):
            return False, "unissued_confirmation"
        if self._events.get(event.request_id) is not event:
            return False, "unissued_confirmation"
        if event.request_id in self._consumed_ids:
            return False, "already_used"
        computed_payload_hash = hash_payload(payload)
        if payload_hash is not None and payload_hash != computed_payload_hash:
            return False, "payload_mismatch"
        payload_hash = computed_payload_hash
        return event.is_valid_for(
            action=action,
            tool=tool,
            session_id=session_id,
            now=self._now(),
            payload_hash=payload_hash,
            current_target_version=current_target_version,
            current_target_hash=current_target_hash,
            request_id=request_id,
            current_target_ref=current_target_ref,
            current_expected_generation=current_expected_generation,
        )

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
        current_target_ref: str | None = None,
        current_expected_generation: int | None = None,
    ) -> tuple[bool, str]:
        with self._consume_lock:
            valid, reason = self._verify_unlocked(
                event=event,
                action=action,
                tool=tool,
                session_id=session_id,
                payload=payload,
                payload_hash=payload_hash,
                current_target_version=current_target_version,
                current_target_hash=current_target_hash,
                request_id=request_id,
                current_target_ref=current_target_ref,
                current_expected_generation=current_expected_generation,
            )
            self._append_audit({
                "event": "verified",
                "request_id": getattr(event, "request_id", None),
                "result": "allowed" if valid else "refused",
                "reason": reason,
                "timestamp": self._now().isoformat(),
            })
            return valid, reason

    def consume(self, event: ConfirmationEvent) -> None:
        """Reject unscoped consumption; use verify_and_consume instead."""
        if not self._owns_event(event):
            raise ValueError("unissued_confirmation")
        raise RuntimeError("unscoped consume is disabled; use verify_and_consume")

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
        current_target_ref: str | None = None,
        current_expected_generation: int | None = None,
    ) -> tuple[bool, str]:
        """Verify provenance and scope, then consume a channel event once.

        This proves channel issuance and one-shot consumption only. It is not
        an external approval receipt and cannot authorize tool dispatch.
        """
        with self._consume_lock:
            valid, reason = self._verify_unlocked(
                event=event,
                action=action,
                tool=tool,
                session_id=session_id,
                payload=payload,
                payload_hash=payload_hash,
                current_target_version=current_target_version,
                current_target_hash=current_target_hash,
                request_id=request_id,
                current_target_ref=current_target_ref,
                current_expected_generation=current_expected_generation,
            )
            self._append_audit({
                "event": "verified",
                "request_id": getattr(event, "request_id", None),
                "result": "allowed" if valid else "refused",
                "reason": reason,
                "timestamp": self._now().isoformat(),
            })
            if valid:
                self._consumed_ids.add(event.request_id)
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

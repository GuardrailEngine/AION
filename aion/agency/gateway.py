"""Bridge between AgencyGate and ConfirmationChannel.

The gateway may issue a scoped request event, but the event is not proof of
external approval. Execution remains fail-closed until a trusted approval
verifier and atomic handler contract are available.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aion.execution.channel import ConfirmationChannel, ConfirmationEvent


@dataclass
class GateDecision:
    """Result of routing a request through the gateway."""

    request_id: str
    is_action: bool
    requires_confirmation: bool
    confirmation: ConfirmationEvent | None
    reason: str
    issued_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AgencyGateway:
    """Coordinates AgencyGate decisions with ConfirmationChannel."""

    def __init__(
        self,
        channel: ConfirmationChannel,
        gate_evaluator: Callable[[dict], tuple[bool, str]],
        target_authority: Any | None = None,
    ) -> None:
        self.channel = channel
        self.gate_evaluator = gate_evaluator
        self.target_authority = target_authority

    @staticmethod
    def _refuse_target(reason: str) -> GateDecision:
        return GateDecision(
            request_id="",
            is_action=True,
            requires_confirmation=False,
            confirmation=None,
            reason=reason,
        )

    @staticmethod
    def _target_identity(target_ref: Any) -> str | None:
        identity = getattr(target_ref, "path", None)
        if isinstance(identity, str) and identity:
            return identity
        return None

    def route(self, request: dict) -> GateDecision:
        """Route a request and issue a scoped event for a confirmed ACTION.

        The caller must obtain external approval, but this repository has no
        trusted mechanism to verify that approval. ExecutionBoundary therefore
        refuses dispatch by default.
        """
        if not isinstance(request, dict):
            raise TypeError("request must be a dict")

        required = ("action", "tool", "session_id", "payload")
        for key in required:
            if key not in request:
                return GateDecision(
                    request_id="",
                    is_action=False,
                    requires_confirmation=False,
                    confirmation=None,
                    reason=f"missing_field:{key}",
                )

        is_action, reason = self.gate_evaluator(request)
        if not is_action:
            return GateDecision(
                request_id="",
                is_action=False,
                requires_confirmation=False,
                confirmation=None,
                reason=reason,
            )

        requested_target_ref = request.get("target_ref")
        caller_target_version = request.get("target_version")
        caller_target_hash = request.get("target_hash")
        target_claimed = (
            requested_target_ref is not None
            or caller_target_version is not None
            or caller_target_hash is not None
        )
        target_identity = None
        target_version = None
        target_hash = None

        if target_claimed:
            if requested_target_ref is None:
                return self._refuse_target("target_ref_required")
            if self.target_authority is None:
                return self._refuse_target("target_authority_required")
            target_identity = self._target_identity(requested_target_ref)
            if target_identity is None:
                return self._refuse_target("target_ref_invalid")

            try:
                snapshot = self.target_authority.snapshot(
                    request["action"], requested_target_ref
                )
            except FileNotFoundError:
                return self._refuse_target("target_not_found")
            # Any authority failure aborts this request; no event is issued.
            except Exception:  # noqa: BLE001
                return self._refuse_target("target_authority_error")

            snapshot_identity = self._target_identity(
                getattr(snapshot, "target_ref", None)
            )
            if snapshot_identity is None:
                return self._refuse_target("target_authority_invalid")
            if snapshot_identity != target_identity:
                return self._refuse_target("target_ref_mismatch")
            target_version = getattr(snapshot, "version", None)
            target_hash = getattr(snapshot, "content_hash", None)
            if not all(
                isinstance(value, str) and value.strip()
                for value in (target_version, target_hash)
            ):
                return self._refuse_target("target_state_unavailable")

        event = self.channel.issue(
            action=request["action"],
            tool=request["tool"],
            session_id=request["session_id"],
            payload=request["payload"],
            target_ref=target_identity,
            target_version=target_version,
            target_hash=target_hash,
        )

        return GateDecision(
            request_id=event.request_id,
            is_action=True,
            requires_confirmation=True,
            confirmation=event,
            reason=reason,
        )

"""Bridge between AgencyGate and ConfirmationChannel.

AgencyGate decides whether a request is ACTION or INFO.
If ACTION, the gateway issues a confirmation via the channel,
returns the confirmation event to the caller, and waits for
external approval before the boundary can execute.

This module does NOT execute tools. It only coordinates
between decision and confirmation issuance.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from aion.execution.channel import (
    ConfirmationChannel,
    ConfirmationEvent,
)


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
    """Coordinates AgencyGate decisions with ConfirmationChannel.

    The gateway expects a `gate_evaluator` callable that returns
    a tuple: (is_action, reason). This keeps the gateway
    independent of the specific AgencyGate implementation.
    """

    def __init__(
        self,
        channel: ConfirmationChannel,
        gate_evaluator: Callable[[dict], tuple[bool, str]],
    ) -> None:
        self.channel = channel
        self.gate_evaluator = gate_evaluator

    def route(
        self,
        request: dict,
    ) -> GateDecision:
        """Route a request: evaluate the gate, and if ACTION,
        issue a confirmation event.

        Does NOT consume the event. The caller must obtain
        external approval and then hand the event to
        ExecutionBoundary.execute().
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

        event = self.channel.issue(
            action=request["action"],
            tool=request["tool"],
            session_id=request["session_id"],
            payload=request["payload"],
            target_version=request.get("target_version"),
            target_hash=request.get("target_hash"),
        )

        return GateDecision(
            request_id=event.request_id,
            is_action=True,
            requires_confirmation=True,
            confirmation=event,
            reason=reason,
        )

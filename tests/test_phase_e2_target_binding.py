"""Phase E.2 evidence: the current architecture lacks an authoritative resolver."""
from __future__ import annotations

import inspect

from aion.agency.gateway import AgencyGateway
from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel, hash_payload


def test_confirmation_channel_can_reject_explicit_target_drift():
    """Existing channel-level target validation remains supported."""
    channel = ConfirmationChannel()
    event = channel.issue(
        "action",
        "tool",
        "s1",
        payload={"x": 1},
        target_version="V1",
        target_hash=hash_payload({"target": "H1"}),
    )

    valid, reason = channel.verify(
        event,
        "action",
        "tool",
        "s1",
        payload={"x": 1},
        current_target_version="V2",
        current_target_hash=hash_payload({"target": "H2"}),
    )
    assert (valid, reason) == (False, "target_drift")
    # Classification: SUPPORTED at ConfirmationChannel only.


def test_execution_boundary_has_no_authoritative_target_resolver_or_current_target_api():
    """E.2 enforcement cannot be implemented without inventing a target source."""
    channel = ConfirmationChannel()
    boundary = ExecutionBoundary(channel, ToolRegistry())
    parameters = inspect.signature(boundary.execute).parameters

    assert "current_target_version" not in parameters
    assert "current_target_hash" not in parameters
    assert "target_snapshot" not in parameters
    assert "target_resolver" not in parameters
    assert not hasattr(boundary, "target_resolver")
    assert not hasattr(boundary, "resolve_target")
    # Classification: NOT ESTABLISHED / STRUCTURAL GAP.


def test_agency_gateway_forwards_caller_target_values_but_does_not_resolve_current_state():
    """Gateway copies request fields; it has no authoritative current-state source."""
    channel = ConfirmationChannel()
    gateway = AgencyGateway(channel, lambda _request: (True, "ACTION"))
    decision = gateway.route(
        {
            "action": "action",
            "tool": "tool",
            "session_id": "s1",
            "payload": {"x": 1},
            "target_version": "V1",
            "target_hash": hash_payload({"target": "H1"}),
        }
    )

    assert decision.confirmation is not None
    assert decision.confirmation.target_version == "V1"
    assert decision.confirmation.target_hash == hash_payload({"target": "H1"})
    assert not hasattr(gateway, "target_resolver")
    assert list(inspect.signature(AgencyGateway.route).parameters) == [
        "self", "request"
    ]
    # Classification: OBSERVED / NOT ESTABLISHED; caller input is not current state.

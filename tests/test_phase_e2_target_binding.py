"""Phase E.2 tests for authoritative target identity and fail-closed execution."""
from __future__ import annotations

import inspect

from aion.agency.gateway import AgencyGateway
from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel, hash_payload
from aion.target.filesystem_authority import FileSystemTargetAuthority, TargetRef


def test_confirmation_channel_rejects_target_drift_and_identity_mismatch():
    channel = ConfirmationChannel()
    payload = {"path": "resource.txt"}
    event = channel.issue(
        "action", "tool", "s1", payload=payload, target_ref="resource.txt",
        target_version="V1", target_hash=hash_payload({"target": "H1"}),
    )

    valid, reason = channel.verify(
        event, "action", "tool", "s1", payload=payload,
        current_target_ref="other.txt", current_target_version="V1",
        current_target_hash=hash_payload({"target": "H1"}),
    )
    assert (valid, reason) == (False, "target_ref_mismatch")
    valid, reason = channel.verify(
        event, "action", "tool", "s1", payload=payload,
        current_target_ref="resource.txt", current_target_version="V2",
        current_target_hash=hash_payload({"target": "H2"}),
    )
    assert (valid, reason) == (False, "target_drift")


def test_execution_boundary_requires_target_ref_and_authority():
    channel = ConfirmationChannel()
    event = channel.issue(
        "action", "tool", "s1", payload={"path": "resource.txt"},
        target_ref="resource.txt", target_version="V1", target_hash="H1",
    )
    boundary = ExecutionBoundary(channel, ToolRegistry())
    parameters = inspect.signature(boundary.execute).parameters
    assert "target_ref" in parameters
    assert "current_target_version" not in parameters
    assert "target_snapshot" not in parameters
    assert not hasattr(boundary, "target_resolver")
    assert boundary.execute(event, "action", "tool", "s1", {"path": "resource.txt"}).reason == "unknown_tool"


def test_gateway_rejects_caller_target_values_without_authoritative_ref():
    channel = ConfirmationChannel()
    gateway = AgencyGateway(channel, lambda _request: (True, "ACTION"))
    decision = gateway.route({
        "action": "action", "tool": "tool", "session_id": "s1",
        "payload": {"x": 1}, "target_version": "V1",
        "target_hash": hash_payload({"target": "H1"}),
    })
    assert decision.confirmation is None
    assert decision.requires_confirmation is False
    assert decision.reason == "target_ref_required"


def test_gateway_uses_authoritative_snapshot_values(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_text("resource")
    target_ref = TargetRef(str(path))
    authority = FileSystemTargetAuthority()
    snapshot = authority.snapshot("action", target_ref)
    gateway = AgencyGateway(
        ConfirmationChannel(), lambda _request: (True, "ACTION"),
        target_authority=authority,
    )
    decision = gateway.route({
        "action": "action", "tool": "tool", "session_id": "s1",
        "payload": {"path": str(path)}, "target_ref": target_ref,
        "target_version": "forged-version", "target_hash": "forged-hash",
    })
    assert decision.confirmation is not None
    assert decision.confirmation.target_ref == target_ref.path
    assert decision.confirmation.target_version == snapshot.version
    assert decision.confirmation.target_hash == snapshot.content_hash

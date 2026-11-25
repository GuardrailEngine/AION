"""Integration tests for AgencyGateway and fail-closed execution."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.agency.gateway import AgencyGateway
from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel
from aion.target.filesystem_authority import FileSystemTargetAuthority, TargetRef


def _read_only_gate(request):
    return False, "info_request"


def _delete_gate(request):
    return (request["action"] == "delete_file", "action_delete")


def _make_registry():
    registry = ToolRegistry()
    calls = []
    registry.register("filesystem", lambda payload: calls.append(payload))
    return registry, calls


def test_info_request_no_confirmation():
    channel = ConfirmationChannel()
    gateway = AgencyGateway(channel, _read_only_gate)
    decision = gateway.route({
        "action": "read_file", "tool": "filesystem", "session_id": "s1",
        "payload": {"path": "file_A.txt"},
    })
    assert decision.is_action is False
    assert decision.requires_confirmation is False
    assert decision.confirmation is None
    assert decision.reason == "info_request"


def test_action_request_issues_scoped_request_event():
    channel = ConfirmationChannel()
    gateway = AgencyGateway(channel, _delete_gate)
    decision = gateway.route({
        "action": "delete_file", "tool": "filesystem", "session_id": "s1",
        "payload": {"path": "file_A.txt"},
    })
    assert decision.is_action is True
    assert decision.requires_confirmation is True
    assert decision.confirmation is not None
    assert decision.reason == "action_delete"
    assert decision.confirmation.action == "delete_file"
    assert decision.confirmation.tool == "filesystem"
    assert decision.confirmation.session_id == "s1"
    assert decision.confirmation.payload_hash is not None


def test_missing_field_rejected():
    gateway = AgencyGateway(ConfirmationChannel(), _delete_gate)
    decision = gateway.route({"action": "delete_file"})
    assert decision.is_action is False
    assert decision.requires_confirmation is False
    assert decision.reason.startswith("missing_field:")


def test_action_flow_fails_closed_without_external_proof():
    channel = ConfirmationChannel()
    registry, calls = _make_registry()
    boundary = ExecutionBoundary(channel, registry)
    gateway = AgencyGateway(channel, _delete_gate)
    payload = {"path": "file_A.txt"}
    decision = gateway.route({
        "action": "delete_file", "tool": "filesystem", "session_id": "s1",
        "payload": payload,
    })

    result = boundary.execute(
        decision.confirmation, "delete_file", "filesystem", "s1", payload
    )
    assert result.executed is False
    assert result.reason == "external_approval_unavailable"
    assert calls == []


def test_payload_mutation_after_gate_rejected():
    channel = ConfirmationChannel()
    registry, calls = _make_registry()
    boundary = ExecutionBoundary(channel, registry)
    gateway = AgencyGateway(channel, _delete_gate)
    decision = gateway.route({
        "action": "delete_file", "tool": "filesystem", "session_id": "s1",
        "payload": {"path": "file_A.txt"},
    })

    result = boundary.execute(
        decision.confirmation, "delete_file", "filesystem", "s1",
        {"path": "file_B.txt"},
    )
    assert result.executed is False
    assert result.reason == "payload_mismatch"
    assert calls == []


def test_target_claim_without_reference_is_refused():
    gateway = AgencyGateway(ConfirmationChannel(), _delete_gate)
    decision = gateway.route({
        "action": "delete_file", "tool": "filesystem", "session_id": "s1",
        "payload": {"path": "file_A.txt"}, "target_version": "v1",
    })
    assert decision.is_action is True
    assert decision.requires_confirmation is False
    assert decision.confirmation is None
    assert decision.reason == "target_ref_required"


def test_target_ref_without_authority_is_refused(tmp_path):
    target_ref = TargetRef(str(tmp_path / "file.txt"))
    gateway = AgencyGateway(ConfirmationChannel(), _delete_gate)
    decision = gateway.route({
        "action": "delete_file", "tool": "filesystem", "session_id": "s1",
        "payload": {"path": target_ref.path}, "target_ref": target_ref,
    })
    assert decision.confirmation is None
    assert decision.reason == "target_authority_required"


def test_target_authority_is_required_even_when_available(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("data")
    target_ref = TargetRef(str(path))
    channel = ConfirmationChannel()
    gateway = AgencyGateway(
        channel, _delete_gate, target_authority=FileSystemTargetAuthority()
    )
    decision = gateway.route({
        "action": "delete_file", "tool": "filesystem", "session_id": "s1",
        "payload": {"path": str(path)}, "target_ref": target_ref,
    })
    assert decision.confirmation is not None
    assert decision.confirmation.target_ref == target_ref.path
    assert decision.confirmation.target_version is not None
    assert decision.confirmation.target_hash is not None

"""Integration tests for AgencyGateway."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.agency.gateway import AgencyGateway
from aion.execution.boundary import (
    ExecutionBoundary,
    ToolRegistry,
)
from aion.execution.channel import ConfirmationChannel


def _read_only_gate(request):
    """INFO gate: everything is read-only."""
    return False, "info_request"


def _delete_gate(request):
    """ACTION gate: any delete is an action."""
    if request["action"] == "delete_file":
        return True, "action_delete"
    return False, "info_request"


def _make_registry():
    reg = ToolRegistry()
    calls = []

    def delete_file(payload):
        calls.append(payload)
        return {"deleted": payload["path"]}

    reg.register("filesystem", delete_file)
    return reg, calls


def test_info_request_no_confirmation():
    channel = ConfirmationChannel()
    gateway = AgencyGateway(channel, _read_only_gate)

    decision = gateway.route({
        "action": "read_file",
        "tool": "filesystem",
        "session_id": "s1",
        "payload": {"path": "file_A.txt"},
    })

    assert decision.is_action is False
    assert decision.requires_confirmation is False
    assert decision.confirmation is None
    assert decision.reason == "info_request"


def test_action_request_issues_confirmation():
    channel = ConfirmationChannel()
    gateway = AgencyGateway(channel, _delete_gate)

    decision = gateway.route({
        "action": "delete_file",
        "tool": "filesystem",
        "session_id": "s1",
        "payload": {"path": "file_A.txt"},
    })

    assert decision.is_action is True
    assert decision.requires_confirmation is True
    assert decision.confirmation is not None
    assert decision.reason == "action_delete"
    assert decision.confirmation.action == "delete_file"
    assert decision.confirmation.tool == "filesystem"
    assert decision.confirmation.session_id == "s1"


def test_missing_field_rejected():
    channel = ConfirmationChannel()
    gateway = AgencyGateway(channel, _delete_gate)

    decision = gateway.route({
        "action": "delete_file",
    })

    assert decision.is_action is False
    assert decision.requires_confirmation is False
    assert decision.reason.startswith("missing_field:")


def test_action_flow_to_execution():
    """End-to-end: gate → confirmation → user approves → boundary executes."""
    channel = ConfirmationChannel()
    reg, calls = _make_registry()
    boundary = ExecutionBoundary(channel, reg)
    gateway = AgencyGateway(channel, _delete_gate)

    decision = gateway.route({
        "action": "delete_file",
        "tool": "filesystem",
        "session_id": "s1",
        "payload": {"path": "file_A.txt"},
    })
    assert decision.is_action is True
    event = decision.confirmation

    result = boundary.execute(
        event=event,
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )

    assert result.executed is True
    assert result.reason == "ok"
    assert calls == [{"path": "file_A.txt"}]


def test_payload_mutation_after_gate_rejected():
    """Gate issues confirmation. Caller mutates payload. Boundary must refuse."""
    channel = ConfirmationChannel()
    reg, calls = _make_registry()
    boundary = ExecutionBoundary(channel, reg)
    gateway = AgencyGateway(channel, _delete_gate)

    decision = gateway.route({
        "action": "delete_file",
        "tool": "filesystem",
        "session_id": "s1",
        "payload": {"path": "file_A.txt"},
    })
    event = decision.confirmation

    result = boundary.execute(
        event=event,
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_B.txt"},
    )

    assert result.executed is False
    assert result.reason == "payload_mismatch"
    assert calls == []


def test_gate_with_target_version():
    channel = ConfirmationChannel()
    gateway = AgencyGateway(channel, _delete_gate)

    decision = gateway.route({
        "action": "delete_file",
        "tool": "filesystem",
        "session_id": "s1",
        "payload": {"path": "file_A.txt"},
        "target_version": "v1",
    })

    assert decision.confirmation.target_version == "v1"

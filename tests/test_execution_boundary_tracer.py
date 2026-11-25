"""Boundary tests documenting that no tool runs without supported proof."""
from __future__ import annotations

from aion.binding import ActionBinding, register_binding
from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel


def test_boundary_does_not_run_tracer_or_tool_without_external_proof():
    action = "runtime_delete"
    register_binding(ActionBinding(action=action, fields=("path",)))
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    calls = []
    registry.register("filesystem", lambda payload: calls.append(payload))
    boundary = ExecutionBoundary(channel, registry)
    payload = {"path": "file_A.txt", "owner": "alice"}
    event = channel.issue(action, "filesystem", "s1", payload=payload)

    result = boundary.execute(event, action, "filesystem", "s1", payload)

    assert result.executed is False
    assert result.reason == "external_approval_unavailable"
    assert calls == []
    assert not [record for record in channel.audit_log() if record.get("event") == "binding_drift"]


def test_boundary_refuses_non_dict_payload_without_dispatch():
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    calls = []
    registry.register("list_processor", lambda payload: calls.append(payload))
    boundary = ExecutionBoundary(channel, registry)
    payload = ["file_A.txt", "file_B.txt"]
    event = channel.issue("list-action", "list_processor", "s1", payload=payload)

    result = boundary.execute(event, "list-action", "list_processor", "s1", payload)

    assert result.executed is False
    assert result.reason == "external_approval_unavailable"
    assert calls == []

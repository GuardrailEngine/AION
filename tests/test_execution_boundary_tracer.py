"""Integration proof for production tracer wiring in ExecutionBoundary."""
from __future__ import annotations

from aion.binding import ActionBinding, TracingRow, register_binding
from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel


def test_execution_boundary_traces_real_tool_and_audits_high_drift():
    register_binding(ActionBinding(action="runtime_delete", fields=("path",)))
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    seen = {}

    def real_tool(payload):
        seen["payload_type"] = type(payload)
        return {"deleted": payload["path"], "owner": payload["owner"]}

    registry.register("filesystem", real_tool)
    boundary = ExecutionBoundary(channel, registry)
    payload = {"path": "file_A.txt", "owner": "alice"}
    event = channel.issue(
        action="runtime_delete",
        tool="filesystem",
        session_id="s1",
        payload=payload,
    )

    result = boundary.execute(
        event=event,
        action="runtime_delete",
        tool="filesystem",
        session_id="s1",
        payload=payload,
    )

    assert result.executed is True
    assert result.reason == "ok"
    assert result.payload == {"deleted": "file_A.txt", "owner": "alice"}
    assert seen["payload_type"] is TracingRow

    drift_records = [
        record
        for record in channel.audit_log()
        if record.get("event") == "binding_drift"
    ]
    assert len(drift_records) == 1
    assert drift_records[0]["risk"] == "HIGH"
    assert drift_records[0]["action"] == "runtime_delete"
    assert drift_records[0]["undeclared_fields"] == ["owner"]
    assert drift_records[0]["request_id"] == event.request_id



def test_execution_boundary_full_row_fallback_has_no_drift():
    """Unknown actions use full-row binding and never report drift."""
    action = "runtime_unregistered_fallback"
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    seen = {}

    def broad_tool(payload):
        seen["payload_type"] = type(payload)
        return {
            "path": payload["path"],
            "owner": payload["owner"],
            "size": payload["size"],
        }

    registry.register("filesystem", broad_tool)
    boundary = ExecutionBoundary(channel, registry)
    payload = {"path": "file_A.txt", "owner": "alice", "size": 100}
    event = channel.issue(
        action=action,
        tool="filesystem",
        session_id="s1",
        payload=payload,
    )

    result = boundary.execute(
        event=event,
        action=action,
        tool="filesystem",
        session_id="s1",
        payload=payload,
    )

    assert result.executed is True
    assert result.reason == "ok"
    assert result.payload == payload
    assert seen["payload_type"] is TracingRow
    assert not [
        record
        for record in channel.audit_log()
        if record.get("event") == "binding_drift"
    ]



def test_execution_boundary_audits_drift_before_tool_error():
    """Undeclared read is audited even when the real tool then fails."""
    from aion.binding import ActionBinding, register_binding

    action = "runtime_error_after_drift"
    register_binding(ActionBinding(action=action, fields=("path",)))
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    seen = {}

    def failing_tool(payload):
        seen["path"] = payload["path"]
        seen["owner"] = payload["owner"]
        raise RuntimeError("simulated failure after field access")

    registry.register("filesystem", failing_tool)
    boundary = ExecutionBoundary(channel, registry)
    payload = {"path": "file_A.txt", "owner": "alice"}
    event = channel.issue(
        action=action,
        tool="filesystem",
        session_id="s1",
        payload=payload,
    )

    result = boundary.execute(
        event=event,
        action=action,
        tool="filesystem",
        session_id="s1",
        payload=payload,
    )

    assert seen == {"path": "file_A.txt", "owner": "alice"}
    assert result.executed is False
    assert result.reason == "tool_error: RuntimeError"

    drift_records = [
        record
        for record in channel.audit_log()
        if record.get("event") == "binding_drift"
    ]
    assert len(drift_records) == 1
    assert drift_records[0]["risk"] == "HIGH"
    assert drift_records[0]["undeclared_fields"] == ["owner"]
    assert drift_records[0]["request_id"] == event.request_id



def test_execution_boundary_passes_non_dict_payload_without_tracing():
    """Non-dict payloads execute unchanged and produce no drift audit."""
    action = "runtime_non_dict_payload"
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    seen = {}

    def list_tool(payload):
        seen["payload"] = payload
        seen["payload_type"] = type(payload)
        return {"length": len(payload)}

    registry.register("list_processor", list_tool)
    boundary = ExecutionBoundary(channel, registry)
    payload = ["file_A.txt", "file_B.txt"]
    event = channel.issue(
        action=action,
        tool="list_processor",
        session_id="s1",
        payload=payload,
    )

    result = boundary.execute(
        event=event,
        action=action,
        tool="list_processor",
        session_id="s1",
        payload=payload,
    )

    assert result.executed is True
    assert result.reason == "ok"
    assert result.payload == {"length": 2}
    assert seen["payload"] == payload
    assert seen["payload_type"] is list
    assert not [
        record
        for record in channel.audit_log()
        if record.get("event") == "binding_drift"
    ]

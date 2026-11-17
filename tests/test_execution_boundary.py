"""Integration tests for fail-closed ExecutionBoundary behavior."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel


def _make_registry():
    registry = ToolRegistry()
    calls = []

    def delete_file(payload):
        calls.append(payload)
        return {"deleted": payload["path"]}

    registry.register("filesystem", delete_file)
    return registry, calls


def test_channel_issued_event_does_not_prove_external_approval():
    channel = ConfirmationChannel()
    registry, calls = _make_registry()
    boundary = ExecutionBoundary(channel, registry)
    payload = {"path": "file_A.txt"}
    event = channel.issue("delete_file", "filesystem", "s1", payload=payload)

    result = boundary.execute(event, "delete_file", "filesystem", "s1", payload)

    assert result.executed is False
    assert result.reason == "external_approval_unavailable"
    assert calls == []


def test_payload_mutation_rejected_before_fail_closed_gate():
    channel = ConfirmationChannel()
    registry, calls = _make_registry()
    boundary = ExecutionBoundary(channel, registry)
    event = channel.issue(
        "delete_file", "filesystem", "s1", payload={"path": "file_A.txt"}
    )

    result = boundary.execute(
        event, "delete_file", "filesystem", "s1", {"path": "file_B.txt"}
    )

    assert result.executed is False
    assert result.reason == "payload_mismatch"
    assert calls == []


def test_unknown_tool_rejected():
    channel = ConfirmationChannel()
    registry, _ = _make_registry()
    boundary = ExecutionBoundary(channel, registry)
    event = channel.issue("delete_file", "unknown_tool", "s1", payload={"path": "x"})

    result = boundary.execute(event, "delete_file", "unknown_tool", "s1", {"path": "x"})

    assert result.executed is False
    assert result.reason == "unknown_tool"


def test_action_mismatch_rejected():
    channel = ConfirmationChannel()
    registry, calls = _make_registry()
    boundary = ExecutionBoundary(channel, registry)
    payload = {"path": "file_A.txt"}
    event = channel.issue("delete_file", "filesystem", "s1", payload=payload)

    result = boundary.execute(event, "read_file", "filesystem", "s1", payload)

    assert result.executed is False
    assert result.reason == "action_mismatch"
    assert calls == []


def test_registered_tool_is_not_called_when_external_proof_is_unavailable():
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    calls = []
    registry.register("failing_tool", lambda payload: calls.append(payload))
    boundary = ExecutionBoundary(channel, registry)
    payload = {"x": 1}
    event = channel.issue("run", "failing_tool", "s1", payload=payload)

    result = boundary.execute(event, "run", "failing_tool", "s1", payload)

    assert result.executed is False
    assert result.reason == "external_approval_unavailable"
    assert calls == []


def test_unverified_execution_attempt_does_not_consume_event_or_dispatch():
    channel = ConfirmationChannel()
    registry, calls = _make_registry()
    boundary = ExecutionBoundary(channel, registry)
    payload = {"path": "file_A.txt"}
    event = channel.issue("delete_file", "filesystem", "s1", payload=payload)

    first = boundary.execute(event, "delete_file", "filesystem", "s1", payload)
    second = boundary.execute(event, "delete_file", "filesystem", "s1", payload)

    assert first.reason == "external_approval_unavailable"
    assert second.reason == "external_approval_unavailable"
    assert first.executed is False and second.executed is False
    assert calls == []

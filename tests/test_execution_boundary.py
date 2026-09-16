"""Integration tests for ExecutionBoundary."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.execution.boundary import (
    ExecutionBoundary,
    ToolRegistry,
)
from aion.execution.channel import ConfirmationChannel


def _make_registry():
    reg = ToolRegistry()
    calls = []

    def delete_file(payload):
        calls.append(payload)
        return {"deleted": payload["path"]}

    reg.register("filesystem", delete_file)
    return reg, calls


def test_execute_valid_confirmation():
    channel = ConfirmationChannel()
    reg, calls = _make_registry()
    boundary = ExecutionBoundary(channel, reg)

    event = channel.issue(
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )
    result = boundary.execute(
        event=event,
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )

    assert result.executed is True
    assert result.reason == "ok"
    assert result.payload == {"deleted": "file_A.txt"}
    assert calls == [{"path": "file_A.txt"}]


def test_execute_payload_mutation_rejected():
    channel = ConfirmationChannel()
    reg, calls = _make_registry()
    boundary = ExecutionBoundary(channel, reg)

    event = channel.issue(
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )
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


def test_execute_unknown_tool_rejected():
    channel = ConfirmationChannel()
    reg, _ = _make_registry()
    boundary = ExecutionBoundary(channel, reg)

    event = channel.issue(
        action="delete_file",
        tool="unknown_tool",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )
    result = boundary.execute(
        event=event,
        action="delete_file",
        tool="unknown_tool",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )

    assert result.executed is False
    assert result.reason == "unknown_tool"


def test_execute_action_mismatch_rejected():
    channel = ConfirmationChannel()
    reg, calls = _make_registry()
    boundary = ExecutionBoundary(channel, reg)

    event = channel.issue(
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )
    result = boundary.execute(
        event=event,
        action="read_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )

    assert result.executed is False
    assert result.reason == "action_mismatch"
    assert calls == []


def test_execute_tool_error_handled():
    channel = ConfirmationChannel()
    reg = ToolRegistry()

    def failing_tool(payload):
        raise RuntimeError("simulated failure")

    reg.register("failing_tool", failing_tool)
    boundary = ExecutionBoundary(channel, reg)

    event = channel.issue(
        action="run",
        tool="failing_tool",
        session_id="s1",
        payload={"x": 1},
    )
    result = boundary.execute(
        event=event,
        action="run",
        tool="failing_tool",
        session_id="s1",
        payload={"x": 1},
    )

    assert result.executed is False
    assert result.reason.startswith("tool_error:")


def test_execute_consumes_confirmation_once():
    channel = ConfirmationChannel()
    reg, calls = _make_registry()
    boundary = ExecutionBoundary(channel, reg)

    event = channel.issue(
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )
    result1 = boundary.execute(
        event=event,
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )
    assert result1.executed is True

    result2 = boundary.execute(
        event=event,
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )
    assert result2.executed is False
    assert result2.reason == "already_used"
    assert calls == [{"path": "file_A.txt"}]

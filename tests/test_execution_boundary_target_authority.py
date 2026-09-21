from __future__ import annotations

from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel
from aion.target.filesystem_authority import FileSystemTargetAuthority, TargetRef


def _setup_tool():
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    called = []

    def tool(payload):
        called.append(payload)
        return "ok"

    registry.register("filesystem-tool", tool)
    return channel, registry, called


def test_unchanged_filesystem_target_allows_execution(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"approved")
    target_ref = TargetRef(str(path))
    authority = FileSystemTargetAuthority()
    approved = authority.snapshot("read_file", target_ref)
    channel, registry, called = _setup_tool()
    event = channel.issue(
        "read_file",
        "filesystem-tool",
        "session-1",
        payload={"path": str(path)},
        target_version=approved.version,
        target_hash=approved.content_hash,
    )

    result = ExecutionBoundary(channel, registry, authority).execute(
        event,
        "read_file",
        "filesystem-tool",
        "session-1",
        {"path": str(path)},
        target_ref=target_ref,
    )

    assert result.executed is True
    assert result.reason == "ok"
    assert called == [{"path": str(path)}]


def test_changed_filesystem_target_refuses_with_target_drift(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"approved")
    target_ref = TargetRef(str(path))
    authority = FileSystemTargetAuthority()
    approved = authority.snapshot("update_file", target_ref)
    channel, registry, called = _setup_tool()
    event = channel.issue(
        "update_file",
        "filesystem-tool",
        "session-1",
        payload={"path": str(path)},
        target_version=approved.version,
        target_hash=approved.content_hash,
    )
    path.write_bytes(b"changed")

    result = ExecutionBoundary(channel, registry, authority).execute(
        event,
        "update_file",
        "filesystem-tool",
        "session-1",
        {"path": str(path)},
        target_ref=target_ref,
    )

    assert result.executed is False
    assert result.reason == "target_drift"
    assert called == []


def test_without_target_authority_preserves_legacy_execution():
    channel, registry, called = _setup_tool()
    event = channel.issue(
        "legacy_action",
        "filesystem-tool",
        "session-1",
        payload={"value": 1},
    )

    result = ExecutionBoundary(channel, registry).execute(
        event,
        "legacy_action",
        "filesystem-tool",
        "session-1",
        {"value": 1},
    )

    assert result.executed is True
    assert result.reason == "ok"
    assert called == [{"value": 1}]


def test_missing_filesystem_target_refuses_without_tool_call(tmp_path):
    target_ref = TargetRef(str(tmp_path / "missing.txt"))
    channel, registry, called = _setup_tool()
    event = channel.issue(
        "read_file",
        "filesystem-tool",
        "session-1",
        payload={"path": target_ref.path},
    )

    result = ExecutionBoundary(
        channel,
        registry,
        FileSystemTargetAuthority(),
    ).execute(
        event,
        "read_file",
        "filesystem-tool",
        "session-1",
        {"path": target_ref.path},
        target_ref=target_ref,
    )

    assert result.executed is False
    assert result.reason == "target_not_found"
    assert called == []

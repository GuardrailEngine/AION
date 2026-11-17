from __future__ import annotations

from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel
from aion.target.filesystem_authority import FileSystemTargetAuthority, TargetRef


def _setup_tool():
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    called = []
    registry.register("filesystem-tool", lambda payload: called.append(payload) or "ok")
    return channel, registry, called


def _issue_bound(channel, target_ref, version, content_hash, payload):
    return channel.issue(
        "read_file", "filesystem-tool", "session-1", payload=payload,
        target_ref=target_ref.path, target_version=version, target_hash=content_hash,
    )


def test_unchanged_target_still_refuses_without_atomic_handler(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"approved")
    target_ref = TargetRef(str(path))
    authority = FileSystemTargetAuthority()
    snapshot = authority.snapshot("read_file", target_ref)
    channel, registry, called = _setup_tool()
    event = _issue_bound(
        channel, target_ref, snapshot.version, snapshot.content_hash,
        {"path": str(path)},
    )

    result = ExecutionBoundary(channel, registry, authority).execute(
        event, "read_file", "filesystem-tool", "session-1", {"path": str(path)},
        target_ref=target_ref,
    )

    assert result.executed is False
    assert result.reason == "atomic_target_execution_unavailable"
    assert called == []


def test_changed_target_refuses_before_atomicity_gate(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"approved")
    target_ref = TargetRef(str(path))
    authority = FileSystemTargetAuthority()
    snapshot = authority.snapshot("update_file", target_ref)
    channel, registry, called = _setup_tool()
    event = channel.issue(
        "update_file", "filesystem-tool", "session-1",
        payload={"path": str(path)}, target_ref=target_ref.path,
        target_version=snapshot.version, target_hash=snapshot.content_hash,
    )
    path.write_bytes(b"changed")

    result = ExecutionBoundary(channel, registry, authority).execute(
        event, "update_file", "filesystem-tool", "session-1", {"path": str(path)},
        target_ref=target_ref,
    )

    assert result.executed is False
    assert result.reason in {"target_drift", "target_hash_mismatch"}
    assert called == []


def test_bound_target_ref_is_required():
    channel, registry, called = _setup_tool()
    payload = {"path": "resource.txt"}
    event = channel.issue(
        "read_file", "filesystem-tool", "session-1", payload=payload,
        target_ref="resource.txt", target_version="v1", target_hash="h1",
    )

    result = ExecutionBoundary(channel, registry, FileSystemTargetAuthority()).execute(
        event, "read_file", "filesystem-tool", "session-1", payload,
    )
    assert result.executed is False
    assert result.reason == "target_ref_required"
    assert called == []


def test_bound_target_authority_is_required():
    channel, registry, called = _setup_tool()
    target_ref = TargetRef("resource.txt")
    payload = {"path": target_ref.path}
    event = channel.issue(
        "read_file", "filesystem-tool", "session-1", payload=payload,
        target_ref=target_ref.path, target_version="v1", target_hash="h1",
    )

    result = ExecutionBoundary(channel, registry).execute(
        event, "read_file", "filesystem-tool", "session-1", payload,
        target_ref=target_ref,
    )
    assert result.executed is False
    assert result.reason == "target_authority_required"
    assert called == []


def test_different_target_identity_is_rejected(tmp_path):
    path_a = tmp_path / "a.txt"
    path_b = tmp_path / "b.txt"
    path_a.write_bytes(b"same")
    path_b.write_bytes(b"same")
    ref_a = TargetRef(str(path_a))
    ref_b = TargetRef(str(path_b))
    authority = FileSystemTargetAuthority()
    snapshot_a = authority.snapshot("read_file", ref_a)
    channel, registry, called = _setup_tool()
    event = channel.issue(
        "read_file", "filesystem-tool", "session-1", payload={"path": str(path_a)},
        target_ref=ref_a.path, target_version=snapshot_a.version,
        target_hash=snapshot_a.content_hash,
    )

    result = ExecutionBoundary(channel, registry, authority).execute(
        event, "read_file", "filesystem-tool", "session-1", {"path": str(path_a)},
        target_ref=ref_b,
    )
    assert result.executed is False
    assert result.reason == "target_ref_mismatch"
    assert called == []


def test_missing_target_refuses_without_tool_call(tmp_path):
    target_ref = TargetRef(str(tmp_path / "missing.txt"))
    channel, registry, called = _setup_tool()
    event = channel.issue(
        "read_file", "filesystem-tool", "session-1",
        payload={"path": target_ref.path}, target_ref=target_ref.path,
        target_version="v1", target_hash="hash-v1",
    )

    result = ExecutionBoundary(
        channel, registry, FileSystemTargetAuthority()
    ).execute(
        event, "read_file", "filesystem-tool", "session-1",
        {"path": target_ref.path}, target_ref=target_ref,
    )
    assert result.executed is False
    assert result.reason == "target_not_found"
    assert called == []

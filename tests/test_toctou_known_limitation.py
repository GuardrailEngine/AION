from __future__ import annotations

import os
from pathlib import Path

from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel
from aion.target.filesystem_authority import FileSystemTargetAuthority, TargetRef


class _MutatingAfterSnapshotAuthority:
    """Simulate a file change immediately after returning the approved snapshot."""

    def __init__(self, path: Path, replacement: bytes) -> None:
        self._authority = FileSystemTargetAuthority()
        self._path = path
        self._replacement = replacement
        self.before_change = None

    def snapshot(self, action: str, target_ref: TargetRef):
        snapshot = self._authority.snapshot(action, target_ref)
        self.before_change = snapshot
        self._path.write_bytes(self._replacement)
        changed_mtime = int(snapshot.version) + 1_000_000_000
        os.utime(self._path, ns=(changed_mtime, changed_mtime))
        return snapshot


def test_toctou_path_refuses_dispatch_when_atomicity_is_unavailable(tmp_path):
    path = tmp_path / "resource.txt"
    content_a = b"content A"
    content_b = b"content B"
    path.write_bytes(content_a)
    target_ref = TargetRef(str(path))
    authority = FileSystemTargetAuthority()
    snapshot_a = authority.snapshot("read_file", target_ref)
    payload = {"path": str(path)}
    channel = ConfirmationChannel()
    event = channel.issue(
        "read_file", "filesystem-reader", "session-1", payload=payload,
        target_ref=target_ref.path, target_version=snapshot_a.version,
        target_hash=snapshot_a.content_hash,
    )

    observed_by_tool = []
    registry = ToolRegistry()
    registry.register(
        "filesystem-reader",
        lambda body: observed_by_tool.append(Path(body["path"]).read_bytes()),
    )
    mutating_authority = _MutatingAfterSnapshotAuthority(path, content_b)
    boundary = ExecutionBoundary(channel, registry, mutating_authority)

    result = boundary.execute(
        event, "read_file", "filesystem-reader", "session-1", payload,
        target_ref=target_ref,
    )
    snapshot_b = authority.snapshot("read_file", target_ref)

    assert mutating_authority.before_change == snapshot_a
    assert snapshot_a.content_hash != snapshot_b.content_hash
    assert path.read_bytes() == content_b
    assert result.executed is False
    assert result.reason == "atomic_target_execution_unavailable"
    assert observed_by_tool == []


def test_filesystem_authority_documents_atomicity_limit():
    docstring = FileSystemTargetAuthority.__doc__ or ""
    assert "TOCTOU" in docstring or "compare-and-execute" in docstring

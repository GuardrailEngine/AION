from __future__ import annotations

import hashlib
import os
from pathlib import Path

from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel
from aion.target.filesystem_authority import (
    FileSystemTargetAuthority,
    TargetRef,
)


class _MutatingAfterSnapshotAuthority:
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


class _RecordingChannel(ConfirmationChannel):
    def __init__(self) -> None:
        super().__init__()
        self.verify_and_consume_target = None

    def verify_and_consume(self, *args, **kwargs):
        self.verify_and_consume_target = (
            kwargs.get("current_target_version"),
            kwargs.get("current_target_hash"),
        )
        return super().verify_and_consume(*args, **kwargs)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_toctou_window_exists_between_snapshot_and_execution(tmp_path):
    """This test documents a known limitation. It proves the window exists.

    It does NOT prove the system is safe against it, and it does NOT propose
    a fix.
    """
    path = tmp_path / "resource.txt"
    content_a = b"content A"
    content_b = b"content B"
    path.write_bytes(content_a)
    target_ref = TargetRef(str(path))
    authority = FileSystemTargetAuthority()

    snapshot_a = authority.snapshot("read_file", target_ref)
    channel = _RecordingChannel()
    event = channel.issue(
        action="read_file",
        tool="filesystem-reader",
        session_id="session-1",
        payload={"path": str(path)},
        target_version=snapshot_a.version,
        target_hash=snapshot_a.content_hash,
    )

    observed_by_tool = []

    def read_tool(payload):
        observed_by_tool.append(Path(payload["path"]).read_bytes())
        return {"observed": observed_by_tool[-1]}

    registry = ToolRegistry()
    registry.register("filesystem-reader", read_tool)
    mutating_authority = _MutatingAfterSnapshotAuthority(path, content_b)
    boundary = ExecutionBoundary(
        channel,
        registry,
        target_authority=mutating_authority,
    )

    result = boundary.execute(
        event,
        "read_file",
        "filesystem-reader",
        "session-1",
        {"path": str(path)},
        target_ref=target_ref,
    )
    snapshot_b = authority.snapshot("read_file", target_ref)

    assert (snapshot_a.version, snapshot_a.content_hash) == (
        str(snapshot_a.version),
        _sha256(content_a),
    )
    assert (snapshot_b.version, snapshot_b.content_hash) == (
        str(snapshot_b.version),
        _sha256(content_b),
    )
    assert (snapshot_a.version, snapshot_a.content_hash) != (
        snapshot_b.version,
        snapshot_b.content_hash,
    )
    assert mutating_authority.before_change == snapshot_a
    assert channel.verify_and_consume_target == (
        snapshot_a.version,
        snapshot_a.content_hash,
    )
    assert observed_by_tool == [content_b]
    assert result.executed is True


def test_known_limitation_is_declared_in_docstring():
    docstring = FileSystemTargetAuthority.__doc__ or ""

    assert "TOCTOU" in docstring or "compare-and-execute" in docstring

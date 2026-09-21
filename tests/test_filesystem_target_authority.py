from __future__ import annotations

import hashlib
import os

import pytest

from aion.target.filesystem_authority import (
    FileSystemTargetAuthority,
    TargetNotFoundError,
    TargetRef,
)


def _expected_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_snapshot_for_existing_file_matches_version_and_content_hash(tmp_path):
    path = tmp_path / "resource.txt"
    content = b"filesystem target\n"
    path.write_bytes(content)
    target_ref = TargetRef(str(path))

    snapshot = FileSystemTargetAuthority().snapshot("read_file", target_ref)
    stat_result = os.stat(path)

    assert snapshot.target_ref == target_ref
    assert snapshot.version == str(stat_result.st_mtime_ns)
    assert snapshot.content_hash == _expected_hash(content)
    assert snapshot.source == "filesystem"


def test_content_change_changes_content_hash(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"before")
    authority = FileSystemTargetAuthority()
    target_ref = TargetRef(str(path))

    before = authority.snapshot("update_file", target_ref)
    path.write_bytes(b"after!")
    after = authority.snapshot("update_file", target_ref)

    assert before.content_hash != after.content_hash


def test_same_size_content_change_changes_mtime_version(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"AAAA")
    authority = FileSystemTargetAuthority()
    target_ref = TargetRef(str(path))

    before = authority.snapshot("update_file", target_ref)
    path.write_bytes(b"BBBB")
    os.utime(path, ns=(before.version and int(before.version) + 1,) * 2)
    after = authority.snapshot("update_file", target_ref)

    assert len(b"AAAA") == len(b"BBBB")
    assert before.version != after.version
    assert before.content_hash != after.content_hash


def test_missing_file_raises_target_not_found_error(tmp_path):
    target_ref = TargetRef(str(tmp_path / "missing.txt"))

    with pytest.raises(TargetNotFoundError, match="Filesystem target not found"):
        FileSystemTargetAuthority().snapshot("read_file", target_ref)


def test_unchanged_file_returns_same_version_and_hash(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"unchanged")
    authority = FileSystemTargetAuthority()
    target_ref = TargetRef(str(path))

    first = authority.snapshot("read_file", target_ref)
    second = authority.snapshot("read_file", target_ref)

    assert first == second

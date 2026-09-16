"""Test ABA detection with target content hashes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.execution.channel import ConfirmationChannel, hash_payload


def test_aba_passes_with_version_only():
    """Document the gap: version-only checking passes an ABA transition."""
    channel = ConfirmationChannel()
    event = channel.issue(
        "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        target_version="v1",
    )
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        current_target_version="v1",
    )
    assert valid is True
    assert reason == "ok"


def test_aba_rejected_with_target_hash():
    """A changed target is rejected even when its version returns to v1."""
    channel = ConfirmationChannel()
    initial_hash = hash_payload({"content": "file_A_initial_content"})
    event = channel.issue(
        "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        target_version="v1",
        target_hash=initial_hash,
    )
    changed_hash = hash_payload({"content": "file_A_changed_content"})
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        current_target_version="v1",
        current_target_hash=changed_hash,
    )
    assert valid is False
    assert reason == "target_hash_mismatch"


def test_unchanged_target_hash_passes():
    """An unchanged target passes when both version and hash match."""
    channel = ConfirmationChannel()
    content_hash = hash_payload({"content": "file_A_initial_content"})
    event = channel.issue(
        "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        target_version="v1",
        target_hash=content_hash,
    )
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        current_target_version="v1",
        current_target_hash=content_hash,
    )
    assert valid is True
    assert reason == "ok"


def test_target_hash_ignored_when_not_bound():
    """An unbound event retains version-only backward compatibility."""
    channel = ConfirmationChannel()
    event = channel.issue(
        "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        target_version="v1",
    )
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        current_target_version="v1",
        current_target_hash="some_other_hash",
    )
    assert valid is True
    assert reason == "ok"

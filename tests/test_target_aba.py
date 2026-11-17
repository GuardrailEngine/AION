"""Tests that target identity and content hash close version-only ABA gaps."""
from __future__ import annotations

import pytest

from aion.execution.channel import ConfirmationChannel, hash_payload


def test_version_only_target_binding_is_rejected():
    channel = ConfirmationChannel()
    with pytest.raises(ValueError, match="target_ref, target_version, and target_hash"):
        channel.issue(
            "delete_file", "fs", "s1", payload={"path": "file_A.txt"},
            target_version="v1",
        )


def test_aba_rejected_with_target_hash_and_identity():
    channel = ConfirmationChannel()
    initial_hash = hash_payload({"content": "file_A_initial_content"})
    event = channel.issue(
        "delete_file", "fs", "s1", payload={"path": "file_A.txt"},
        target_ref="file_A.txt", target_version="v1", target_hash=initial_hash,
    )
    changed_hash = hash_payload({"content": "file_A_changed_content"})
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload={"path": "file_A.txt"},
        current_target_ref="file_A.txt", current_target_version="v1",
        current_target_hash=changed_hash,
    ) == (False, "target_hash_mismatch")


def test_unchanged_target_requires_all_bound_values():
    channel = ConfirmationChannel()
    content_hash = hash_payload({"content": "file_A_initial_content"})
    payload = {"path": "file_A.txt"}
    event = channel.issue(
        "delete_file", "fs", "s1", payload=payload,
        target_ref="file_A.txt", target_version="v1", target_hash=content_hash,
    )
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload=payload,
        current_target_ref="file_A.txt", current_target_version="v1",
        current_target_hash=content_hash,
    ) == (True, "ok")


def test_target_hash_cannot_be_ignored_when_current_state_is_missing():
    channel = ConfirmationChannel()
    payload = {"path": "file_A.txt"}
    event = channel.issue(
        "delete_file", "fs", "s1", payload=payload,
        target_ref="file_A.txt", target_version="v1", target_hash="h1",
    )
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload=payload,
        current_target_ref="file_A.txt", current_target_version="v1",
    ) == (False, "target_state_unavailable")

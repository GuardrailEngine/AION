"""Tests for strict target reference, version, and hash comparisons."""
from __future__ import annotations

import pytest

from aion.execution.channel import ConfirmationChannel


def test_target_drift_between_approval_and_execution():
    channel = ConfirmationChannel()
    payload = {"path": "file_A.txt"}
    event = channel.issue(
        "delete_file", "fs", "s1", payload=payload,
        target_ref="file_A.txt", target_version="v1", target_hash="h1",
    )
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1", payload=payload,
        current_target_ref="file_A.txt", current_target_version="v2",
        current_target_hash="h2",
    )
    assert (valid, reason) == (False, "target_drift")
    assert event.used is False


def test_unchanged_target_scope_is_validated():
    channel = ConfirmationChannel()
    payload = {"path": "file_A.txt"}
    event = channel.issue(
        "delete_file", "fs", "s1", payload=payload,
        target_ref="file_A.txt", target_version="v1", target_hash="h1",
    )
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload=payload,
        current_target_ref="file_A.txt", current_target_version="v1",
        current_target_hash="h1",
    ) == (True, "ok")


def test_target_state_missing_is_rejected():
    channel = ConfirmationChannel()
    payload = {"path": "file_A.txt"}
    event = channel.issue(
        "delete_file", "fs", "s1", payload=payload,
        target_ref="file_A.txt", target_version="v1", target_hash="h1",
    )
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload=payload,
    ) == (False, "target_state_unavailable")


def test_verify_and_consume_path_is_one_shot():
    channel = ConfirmationChannel()
    payload = {"path": "file_A.txt"}
    event = channel.issue("delete_file", "fs", "s1", payload=payload)
    assert channel.verify_and_consume(
        event, "delete_file", "fs", "s1", payload=payload
    ) == (True, "ok")
    assert event.used is True
    assert channel.verify_and_consume(
        event, "delete_file", "fs", "s1", payload=payload
    ) == (False, "already_used")


def test_partial_target_binding_is_rejected_at_issue():
    channel = ConfirmationChannel()
    with pytest.raises(ValueError):
        channel.issue(
            "delete_file", "fs", "s1", payload={"path": "a"},
            target_version="v1",
        )

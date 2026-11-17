"""Unit tests for ConfirmationChannel provenance, scope, and one-shot use."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.execution.channel import (
    ConfirmationChannel,
    ConfirmationEvent,
    hash_payload,
)


def test_expired_confirmation():
    channel = ConfirmationChannel(ttl_seconds=1)
    issued_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    with patch.object(
        channel,
        "_now",
        side_effect=[issued_at, datetime.now(timezone.utc), datetime.now(timezone.utc)],
    ):
        event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
        valid, reason = channel.verify(
            event, "delete_file", "fs", "s1", payload={"p": "a"}
        )
    assert not valid
    assert reason == "expired"


def test_caller_constructed_confirmation_is_rejected():
    channel = ConfirmationChannel()
    now = datetime.now(timezone.utc)
    forged = ConfirmationEvent(
        request_id="not-issued", action="delete_file", tool="fs",
        session_id="s1", nonce="caller-chosen", issued_at=now,
        expires_at=now + timedelta(minutes=1),
        payload_hash=hash_payload({"p": "a"}),
    )
    valid, reason = channel.verify(
        forged, "delete_file", "fs", "s1", payload={"p": "a"}
    )
    consumed, consume_reason = channel.verify_and_consume(
        forged, "delete_file", "fs", "s1", payload={"p": "a"}
    )
    assert (valid, reason) == (False, "unissued_confirmation")
    assert (consumed, consume_reason) == (False, "unissued_confirmation")


def test_event_issued_by_another_channel_is_rejected():
    issuing_channel = ConfirmationChannel()
    other_channel = ConfirmationChannel()
    event = issuing_channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    assert other_channel.verify(
        event, "delete_file", "fs", "s1", payload={"p": "a"}
    ) == (False, "unissued_confirmation")


def test_caller_supplied_payload_hash_cannot_override_actual_payload():
    channel = ConfirmationChannel()
    payload = {"path": "approved.txt"}
    forged_hash = hash_payload({"path": "different.txt"})

    with pytest.raises(ValueError, match="payload_hash does not match payload"):
        channel.issue(
            "delete_file", "fs", "s1", payload=payload,
            payload_hash=forged_hash,
        )

    event = channel.issue("delete_file", "fs", "s1", payload=payload)
    assert channel.verify(
        event,
        "delete_file",
        "fs",
        "s1",
        payload=payload,
        payload_hash=forged_hash,
    ) == (False, "payload_mismatch")


def test_request_id_mismatch():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload={"p": "a"},
        request_id="other_id",
    ) == (False, "request_id_mismatch")


def test_action_mismatch():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    assert channel.verify(event, "delete_db", "fs", "s1", payload={"p": "a"}) == (
        False, "action_mismatch"
    )


def test_tool_mismatch():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    assert channel.verify(event, "delete_file", "db", "s1", payload={"p": "a"}) == (
        False, "tool_mismatch"
    )


def test_session_mismatch():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    assert channel.verify(event, "delete_file", "fs", "s2", payload={"p": "a"}) == (
        False, "session_mismatch"
    )


def test_payload_mutation_before_consume():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"path": "file_A.txt"})
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1", payload={"path": "file_B.txt"}
    )
    assert (valid, reason) == (False, "payload_mismatch")
    assert event.used is False


def test_payload_mutation_after_consume_is_rejected_as_replay():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"path": "file_A.txt"})
    assert channel.verify_and_consume(
        event, "delete_file", "fs", "s1", payload={"path": "file_A.txt"}
    ) == (True, "ok")
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload={"path": "file_B.txt"}
    ) == (False, "already_used")


def test_unchanged_payload_is_accepted_for_scope_validation():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"path": "file_A.txt"})
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload={"path": "file_A.txt"}
    ) == (True, "ok")


def test_key_ordering_does_not_change_payload_hash():
    assert hash_payload({"a": 1, "b": 2}) == hash_payload({"b": 2, "a": 1})


def test_nested_value_tampering_is_rejected():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"user": {"id": 1}})
    assert channel.verify(
        event, "action", "tool", "s1", payload={"user": {"id": 2}}
    ) == (False, "payload_mismatch")


def test_list_ordering_is_semantically_significant():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"items": ["a", "b"]})
    assert channel.verify(
        event, "action", "tool", "s1", payload={"items": ["b", "a"]}
    ) == (False, "payload_mismatch")


def test_target_binding_requires_reference_version_and_hash():
    channel = ConfirmationChannel()
    with pytest.raises(ValueError, match="target_ref, target_version, and target_hash"):
        channel.issue(
            "delete_file", "fs", "s1", payload={"path": "a"},
            target_version="v1", target_hash="h1",
        )


def test_target_binding_requires_current_state_and_matching_identity():
    channel = ConfirmationChannel()
    event = channel.issue(
        "delete_file", "fs", "s1", payload={"path": "a"},
        target_ref="/a", target_version="v1", target_hash="h1",
    )
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload={"path": "a"}
    ) == (False, "target_state_unavailable")
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload={"path": "a"},
        current_target_ref="/b", current_target_version="v1", current_target_hash="h1",
    ) == (False, "target_ref_mismatch")
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload={"path": "a"},
        current_target_ref="/a", current_target_version="v2", current_target_hash="h1",
    ) == (False, "target_drift")
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload={"path": "a"},
        current_target_ref="/a", current_target_version="v1", current_target_hash="h2",
    ) == (False, "target_hash_mismatch")
    assert channel.verify(
        event, "delete_file", "fs", "s1", payload={"path": "a"},
        current_target_ref="/a", current_target_version="v1", current_target_hash="h1",
    ) == (True, "ok")


def test_unscoped_consume_is_disabled():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"a": 1})
    with pytest.raises(RuntimeError, match="unscoped consume is disabled"):
        channel.consume(event)
    assert channel.verify(event, "action", "tool", "s1", payload={"a": 1}) == (
        True, "ok"
    )


def test_consume_twice_is_rejected_even_if_event_used_flag_is_reset():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"a": 1})
    assert channel.verify_and_consume(
        event, "action", "tool", "s1", payload={"a": 1}
    ) == (True, "ok")
    object.__setattr__(event, "used", False)
    assert channel.verify_and_consume(
        event, "action", "tool", "s1", payload={"a": 1}
    ) == (False, "already_used")


def test_concurrent_consumers_have_exactly_one_success():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"a": 1})

    def consume(_):
        return channel.verify_and_consume(
            event, "action", "tool", "s1", payload={"a": 1}
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(consume, range(64)))
    assert outcomes.count((True, "ok")) == 1
    assert outcomes.count((False, "already_used")) == 63
    consumed = [record for record in channel.audit_log() if record["event"] == "consumed"]
    assert len(consumed) == 1


def test_invalid_ttl_rejected():
    with pytest.raises(ValueError):
        ConfirmationChannel(ttl_seconds=-1)


def test_audit_log_records_events():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"a": 1})
    channel.verify(event, "action", "tool", "s1", payload={"a": 1})
    log = channel.audit_log()
    assert len(log) >= 2
    assert log[0]["event"] == "issued"

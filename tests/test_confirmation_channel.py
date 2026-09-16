"""Unit tests for ConfirmationChannel."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.execution.channel import (
    ConfirmationChannel,
    ConfirmationEvent,
    hash_payload,
)


def test_expired_confirmation():
    channel = ConfirmationChannel(ttl_seconds=1)
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    event.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    valid, reason = channel.verify(event, "delete_file", "fs", "s1", payload={"p": "a"})
    assert not valid
    assert reason == "expired"


def test_already_used():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    channel.consume(event)
    valid, reason = channel.verify(event, "delete_file", "fs", "s1", payload={"p": "a"})
    assert not valid
    assert reason == "already_used"


def test_request_id_mismatch():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1", payload={"p": "a"},
        request_id="other_id",
    )
    assert not valid
    assert reason == "request_id_mismatch"


def test_action_mismatch():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    valid, reason = channel.verify(event, "delete_db", "fs", "s1", payload={"p": "a"})
    assert not valid
    assert reason == "action_mismatch"


def test_tool_mismatch():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    valid, reason = channel.verify(event, "delete_file", "db", "s1", payload={"p": "a"})
    assert not valid
    assert reason == "tool_mismatch"


def test_session_mismatch():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"p": "a"})
    valid, reason = channel.verify(event, "delete_file", "fs", "s2", payload={"p": "a"})
    assert not valid
    assert reason == "session_mismatch"


def test_payload_mutation_before_consume():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"path": "file_A.txt"})
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1",
        payload={"path": "file_B.txt"},
    )
    assert not valid
    assert reason == "payload_mismatch"
    assert event.used is False


def test_payload_mutation_after_consume():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"path": "file_A.txt"})
    channel.consume(event)
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1",
        payload={"path": "file_B.txt"},
    )
    assert not valid
    assert reason == "already_used"


def test_unchanged_payload_is_accepted():
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "fs", "s1", payload={"path": "file_A.txt"})
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
    )
    assert valid
    assert reason == "ok"


def test_key_ordering_does_not_change_payload_hash():
    h1 = hash_payload({"a": 1, "b": 2})
    h2 = hash_payload({"b": 2, "a": 1})
    assert h1 == h2


def test_nested_value_tampering_is_rejected():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"user": {"id": 1}})
    valid, reason = channel.verify(
        event, "action", "tool", "s1",
        payload={"user": {"id": 2}},
    )
    assert not valid
    assert reason == "payload_mismatch"


def test_list_ordering_is_semantically_significant():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"items": ["a", "b"]})
    valid, reason = channel.verify(
        event, "action", "tool", "s1",
        payload={"items": ["b", "a"]},
    )
    assert not valid
    assert reason == "payload_mismatch"


def test_invalid_ttl_rejected():
    try:
        ConfirmationChannel(ttl_seconds=-1)
        assert False, "Should have raised"
    except ValueError:
        pass


def test_audit_log_records_events():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"a": 1})
    channel.verify(event, "action", "tool", "s1", payload={"a": 1})
    log = channel.audit_log()
    assert len(log) >= 2
    assert log[0]["event"] == "issued"


def test_consume_twice_raises():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"a": 1})
    channel.consume(event)
    try:
        channel.consume(event)
        assert False, "Should have raised"
    except ValueError:
        pass

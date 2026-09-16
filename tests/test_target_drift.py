"""Test target version drift — the CAS layer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.execution.channel import ConfirmationChannel


def test_target_drift_between_approve_and_execute():
    channel = ConfirmationChannel()
    event = channel.issue(
        "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        target_version="v1",
    )
    valid, reason = channel.verify(
        event, "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
        current_target_version="v2",
    )
    assert not valid
    assert reason == "target_drift"
    assert event.used is False


def test_unchanged_target_is_accepted():
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
    assert valid
    assert reason == "ok"


def test_verify_and_consume_path():
    channel = ConfirmationChannel()
    event = channel.issue(
        "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
    )
    valid, reason = channel.verify_and_consume(
        event, "delete_file", "fs", "s1",
        payload={"path": "file_A.txt"},
    )
    assert valid
    assert reason == "ok"
    assert event.used is True

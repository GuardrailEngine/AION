"""Focused Phase E.1 tests for atomic consume and immutable confirmations."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel, hash_payload


def _start_two_consumers_together() -> threading.Barrier:
    return threading.Barrier(2)


def test_concurrent_double_consume_has_exactly_one_success_and_one_rejection():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"x": 1})
    start_barrier = _start_two_consumers_together()

    def consume():
        start_barrier.wait(timeout=5)
        return channel.verify_and_consume(
            event,
            action="action",
            tool="tool",
            session_id="s1",
            payload={"x": 1},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: consume(), (0, 1)))

    assert outcomes.count((True, "ok")) == 1
    assert outcomes.count((False, "already_used")) == 1
    consumed = [record for record in channel.audit_log() if record["event"] == "consumed"]
    assert len(consumed) == 1


def test_rejected_concurrent_consumer_cannot_execute_tool():
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    calls = []

    def tool(payload):
        calls.append(payload)
        return "executed"

    registry.register("tool", tool)
    boundary = ExecutionBoundary(channel, registry)
    event = channel.issue("action", "tool", "s1", payload={"x": 1})
    start_barrier = _start_two_consumers_together()

    def execute():
        start_barrier.wait(timeout=5)
        return boundary.execute(event, "action", "tool", "s1", {"x": 1})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(), (0, 1)))

    assert sum(result.executed for result in results) == 1
    assert sorted(result.reason for result in results) == ["already_used", "ok"]
    assert calls == [{"x": 1}]


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", "changed-request"),
        ("action", "changed-action"),
        ("tool", "changed-tool"),
        ("payload_hash", hash_payload({"x": 2})),
        ("target_version", "V2"),
        ("target_hash", hash_payload({"target": "H2"})),
    ],
)
def test_confirmation_identity_fields_are_immutable(field, value):
    channel = ConfirmationChannel()
    event = channel.issue(
        "action",
        "tool",
        "s1",
        payload={"x": 1},
        target_version="V1",
        target_hash=hash_payload({"target": "H1"}),
    )

    with pytest.raises(FrozenInstanceError):
        setattr(event, field, value)

    assert getattr(event, field) != value


def test_immutable_event_preserves_payload_hash_contract():
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"b": 2, "a": 1})
    valid, reason = channel.verify(
        event,
        "action",
        "tool",
        "s1",
        payload={"a": 1, "b": 2},
    )
    assert (valid, reason) == (True, "ok")
    assert event.payload_hash == hash_payload({"a": 1, "b": 2})

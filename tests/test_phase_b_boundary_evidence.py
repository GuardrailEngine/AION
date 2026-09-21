"""Phase B evidence tests: observe current boundary seams without fixing them."""
from __future__ import annotations

import inspect
import threading
from collections import UserDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from aion.binding import TracingRow
from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel, hash_payload
from aion_core import AuditLog, Pipeline, StubProvider, execute_decision


class CustomMapping(UserDict):
    """A non-dict Mapping implementation for boundary observation."""


def _registry_with_recorder():
    registry = ToolRegistry()
    calls = []

    def tool(payload):
        calls.append(payload)
        return {"ok": True}

    registry.register("tool-a", tool)
    return registry, calls


def test_target_binding_is_proven_at_channel_but_not_boundary_api():
    """Target checks work in the channel; Boundary has no current-target inputs."""
    channel = ConfirmationChannel()
    event = channel.issue(
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "a.txt"},
        target_version="v1",
        target_hash=hash_payload({"content": "initial"}),
    )

    valid, reason = channel.verify(
        event,
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "a.txt"},
        current_target_version="v1",
        current_target_hash=hash_payload({"content": "initial"}),
    )
    assert (valid, reason) == (True, "ok")

    stale, stale_reason = channel.verify(
        event,
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "a.txt"},
        current_target_version="v2",
        current_target_hash=hash_payload({"content": "changed"}),
    )
    assert (stale, stale_reason) == (False, "target_drift")

    parameters = inspect.signature(ExecutionBoundary.execute).parameters
    assert "current_target_version" not in parameters
    assert "current_target_hash" not in parameters


def test_verify_and_consume_forced_race_allows_one_consumer_only():
    """Force overlapping verification and assert thread-scoped atomic consume."""
    channel = ConfirmationChannel()
    event = channel.issue("delete_file", "filesystem", "s1", payload={"path": "a"})
    start_barrier = threading.Barrier(2)

    def consume_once():
        start_barrier.wait(timeout=5)
        return channel.verify_and_consume(
            event,
            action="delete_file",
            tool="filesystem",
            session_id="s1",
            payload={"path": "a"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _ignored: consume_once(), (0, 1)))

    assert results.count((True, "ok")) == 1
    assert results.count((False, "already_used")) == 1
    assert event.used is True


def test_confirmation_event_identity_fields_are_immutable():
    """Issued event identity fields cannot be changed after issuance."""
    channel = ConfirmationChannel()
    event = channel.issue(
        "action-a",
        "tool-a",
        "s1",
        payload={"x": 1},
        target_version="v1",
        target_hash=hash_payload({"target": "v1"}),
    )
    mutations = {
        "request_id": "mutated-request",
        "action": "action-b",
        "tool": "tool-b",
        "payload_hash": hash_payload({"x": 2}),
        "target_version": "v2",
        "target_hash": hash_payload({"target": "v2"}),
    }
    for field, value in mutations.items():
        with pytest.raises(FrozenInstanceError):
            setattr(event, field, value)


def test_tool_registry_dispatch_is_tool_keyed_while_confirmation_checks_action_and_tool():
    """The boundary checks both fields, but registry lookup itself is tool-only."""
    registry, calls = _registry_with_recorder()
    channel = ConfirmationChannel()
    boundary = ExecutionBoundary(channel, registry)

    first = channel.issue("action-a", "tool-a", "s1", payload={"x": 1})
    first_result = boundary.execute(first, "action-a", "tool-a", "s1", {"x": 1})
    assert first_result.executed is True

    second = channel.issue("action-b", "tool-a", "s1", payload={"x": 2})
    second_result = boundary.execute(second, "action-b", "tool-a", "s1", {"x": 2})
    assert second_result.executed is True
    assert len(calls) == 2

    mismatched = channel.issue("action-a", "tool-a", "s1", payload={"x": 3})
    mismatch_result = boundary.execute(
        mismatched, "action-b", "tool-a", "s1", {"x": 3}
    )
    assert mismatch_result.executed is False
    assert mismatch_result.reason == "action_mismatch"

    assert list(inspect.signature(ToolRegistry.register).parameters) == [
        "self", "name", "fn"
    ]


def test_pipeline_has_no_automatic_confirmation_boundary_path(tmp_path):
    """Current Pipeline returns a decision; it does not construct the execution path."""
    pipeline = Pipeline(
        StubProvider(),
        audit=AuditLog(path=str(tmp_path / "decisions.jsonl")),
    )
    decision = pipeline.process("ما هي عاصمة فرنسا؟")
    assert decision.request_id
    assert not hasattr(pipeline, "channel")
    assert not hasattr(pipeline, "boundary")

    with pytest.raises(NotImplementedError):
        execute_decision(decision, tool=None)


def test_non_dict_mapping_bypasses_tracing_wrapper_in_boundary():
    """A custom Mapping is not wrapped by the current dict-only boundary branch."""
    mapping = CustomMapping({"path": "a.txt", "owner": "alice"})
    traced = TracingRow(mapping)
    _ = traced["owner"]
    assert traced.accessed_fields == frozenset({"owner"})

    registry = ToolRegistry()
    seen = []

    def tool(payload):
        seen.append(type(payload))
        return "ok"

    registry.register("mapping-tool", tool)
    channel = ConfirmationChannel()
    boundary = ExecutionBoundary(channel, registry)
    event = channel.issue(
        "mapping-action",
        "mapping-tool",
        "s1",
        payload_hash=hash_payload(dict(mapping)),
    )

    with pytest.raises(TypeError):
        boundary.execute(event, "mapping-action", "mapping-tool", "s1", mapping)
    assert seen == []
    assert isinstance(mapping, UserDict)


def test_channel_audit_records_are_mutable_and_process_local():
    """Audit output is a shallow list copy over mutable in-memory records."""
    channel = ConfirmationChannel()
    channel.issue("action", "tool", "s1", payload={"x": 1})
    records = channel.audit_log()
    records[0]["event"] = "tampered-in-caller"
    assert channel.audit_log()[0]["event"] == "tampered-in-caller"

    other_channel = ConfirmationChannel()
    assert other_channel.audit_log() == []
    assert not hasattr(channel, "verify_audit_integrity")
    assert not hasattr(channel, "audit_signature")

"""Phase C hardening evidence: precise observations, no production fixes."""
from __future__ import annotations

import inspect
import threading
from collections import UserDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from aion.binding import (
    ActionBinding,
    TracingRow,
    detect_binding_drift,
    register_binding,
)
from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel, hash_payload
from aion_core import AuditLog, Pipeline, StubProvider, execute_decision


class CustomMapping(UserDict):
    """A non-dict Mapping implementation used only for evidence."""


def test_execution_boundary_target_binding_is_structurally_unestablished():
    """Channel proves drift rejection; Boundary lacks current-target inputs."""
    channel = ConfirmationChannel()
    event = channel.issue(
        "delete_file",
        "filesystem",
        "s1",
        payload={"path": "a.txt"},
        target_version="V1",
        target_hash=hash_payload({"content": "H1"}),
    )

    proven, reason = channel.verify(
        event,
        "delete_file",
        "filesystem",
        "s1",
        payload={"path": "a.txt"},
        current_target_version="V2",
        current_target_hash=hash_payload({"content": "H2"}),
    )
    assert (proven, reason) == (False, "target_drift")

    boundary_parameters = inspect.signature(ExecutionBoundary.execute).parameters
    assert "current_target_version" not in boundary_parameters
    assert "current_target_hash" not in boundary_parameters
    # Classification: TARGET BINDING AT CONFIRMATION = PROVEN;
    # TARGET BINDING AT EXECUTION = NOT ESTABLISHED / STRUCTURAL GAP.


def test_single_use_forced_overlap_allows_one_consumer_only():
    """A deterministic overlap permits one thread-scoped consume transition."""
    channel = ConfirmationChannel()
    event = channel.issue("action", "tool", "s1", payload={"x": 1})
    start_barrier = threading.Barrier(2)

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
    assert event.used is True
    # Classification: OBSERVED / PROVEN BY TEST for this schedule;
    # atomicity across all races/processes remains NOT ESTABLISHED.


def test_confirmation_event_identity_fields_are_immutable():
    """All requested identity fields remain fixed after issuance."""
    channel = ConfirmationChannel()
    event = channel.issue(
        "action-a",
        "tool-a",
        "session-a",
        payload={"x": 1},
        target_version="V1",
        target_hash=hash_payload({"target": "H1"}),
    )

    mutations = {
        "request_id": "mutated-request",
        "action": "action-b",
        "tool": "tool-b",
        "payload_hash": hash_payload({"x": 2}),
        "target_version": "V2",
        "target_hash": hash_payload({"target": "H2"}),
    }
    for field, value in mutations.items():
        with pytest.raises(FrozenInstanceError):
            setattr(event, field, value)


def test_action_tool_identity_is_checked_by_channel_but_lookup_is_tool_only():
    """Confirmation checks both strings; ToolRegistry resolves only by tool."""
    channel = ConfirmationChannel()
    event_a = channel.issue("action-a", "shared-tool", "s1", payload={"x": 1})
    event_b = channel.issue("action-b", "shared-tool", "s1", payload={"x": 2})

    valid_a, reason_a = channel.verify(
        event_a, "action-a", "shared-tool", "s1", payload={"x": 1}
    )
    valid_b, reason_b = channel.verify(
        event_b, "action-b", "shared-tool", "s1", payload={"x": 2}
    )
    wrong_action, wrong_reason = channel.verify(
        event_a, "action-b", "shared-tool", "s1", payload={"x": 1}
    )
    assert (valid_a, reason_a) == (True, "ok")
    assert (valid_b, reason_b) == (True, "ok")
    assert (wrong_action, wrong_reason) == (False, "action_mismatch")

    registry = ToolRegistry()
    registry.register("shared-tool", lambda payload: payload)
    assert registry.has("shared-tool") is True
    assert list(inspect.signature(ToolRegistry.get).parameters) == ["self", "name"]
    # Classification: PROVEN BY TEST / CURRENTLY SUPPORTED for the observed API.


def test_payload_type_matrix_separates_hashing_wrapping_and_observability():
    """Dict reaches tracing; Mapping and TracingRow do not reach the tool path."""
    register_binding(ActionBinding("phase_c_dict", ("path",)))
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    seen = {}

    def dict_tool(payload):
        seen["type"] = type(payload)
        _ = payload["owner"]
        return "ok"

    registry.register("dict-tool", dict_tool)
    boundary = ExecutionBoundary(channel, registry)
    dict_payload = {"path": "a.txt", "owner": "alice"}
    dict_event = channel.issue(
        "phase_c_dict", "dict-tool", "s1", payload=dict_payload
    )
    dict_result = boundary.execute(
        dict_event, "phase_c_dict", "dict-tool", "s1", dict_payload
    )
    assert dict_result.executed is True
    assert seen["type"] is TracingRow
    assert any(
        record.get("event") == "binding_drift"
        and record.get("risk") == "HIGH"
        for record in channel.audit_log()
    )

    mapping_payload = CustomMapping(dict_payload)
    traced_payload = TracingRow(dict_payload)
    _ = traced_payload["owner"]
    assert traced_payload.accessed_fields == frozenset({"owner"})
    with pytest.raises(TypeError):
        hash_payload(mapping_payload)
    with pytest.raises(TypeError):
        hash_payload(traced_payload)

    mapping_event = channel.issue(
        "phase_c_mapping",
        "dict-tool",
        "s1",
        payload_hash=hash_payload(dict_payload),
    )
    with pytest.raises(TypeError):
        boundary.execute(
            mapping_event,
            "phase_c_mapping",
            "dict-tool",
            "s1",
            mapping_payload,
        )
    assert seen["type"] is TracingRow
    # Classification: dict tracing is PROVEN; Mapping/TracingRow boundary path
    # is NOT ESTABLISHED / STRUCTURAL GAP in the current implementation.


def test_audit_records_are_shallow_mutable_process_local_without_integrity_check():
    """Mutating returned audit records mutates channel state; no verifier exists."""
    channel = ConfirmationChannel()
    channel.issue("action", "tool", "s1", payload={"x": 1})
    records = channel.audit_log()
    records[0]["event"] = "caller-mutated"
    assert channel.audit_log()[0]["event"] == "caller-mutated"

    other_channel = ConfirmationChannel()
    assert other_channel.audit_log() == []
    assert not hasattr(channel, "verify_audit_integrity")
    assert not hasattr(channel, "audit_signature")
    # Classification: PROVEN BY TEST for mutability/process-local behavior;
    # integrity is NOT ESTABLISHED.


def test_pipeline_does_not_automatically_reach_confirmation_boundary(tmp_path):
    """Pipeline produces a Decision; the missing execution path is not built."""
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
    # Classification: NOT ESTABLISHED / STRUCTURAL GAP; no missing path added.


def test_detect_binding_drift_is_observable_only_for_declared_mapping_accesses():
    """Direct tracer evidence distinguishes detection from enforcement."""
    register_binding(ActionBinding("phase_c_drift", ("path",)))
    traced = TracingRow({"path": "a.txt", "secret": "value"})
    _ = traced["secret"]
    finding = detect_binding_drift(traced.accessed_fields, ActionBinding(
        "phase_c_drift", ("path",)
    ))
    assert finding is not None
    assert finding["severity"] == "HIGH"
    assert finding["undeclared_fields"] == ["secret"]
    # Classification: PROVEN BY TEST; current policy is observation, not blocking.

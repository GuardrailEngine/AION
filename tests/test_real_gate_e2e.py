"""End-to-end: real AgencyGate -> adapter -> gateway -> fail-closed boundary."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.agency.gateway import AgencyGateway
from aion.agency.real_gate_adapter import make_evaluator, map_request_for_real_gate
from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel
from aion.target.filesystem_authority import FileSystemTargetAuthority, TargetRef
from tests.fixtures_core import (
    make_constitution,
    make_critique,
    make_reasoning,
    make_request,
    make_risk,
)


def _make_real_gate_request(target_ref=None):
    return map_request_for_real_gate(
        action="delete_file", tool="filesystem", session_id="s1",
        payload={"path": "file_A.txt"}, req=make_request(),
        reasoning=make_reasoning(), critique=make_critique(), risk=make_risk(),
        constitution=make_constitution(), target_ref=target_ref,
    )


def _make_registry():
    registry = ToolRegistry()
    calls = []
    registry.register("filesystem", lambda payload: calls.append(payload))
    return registry, calls


def test_real_gate_evaluator_uses_canonical_core_types():
    is_action, reason = make_evaluator()(_make_real_gate_request())
    assert is_action is True
    assert reason == "action_requires_confirmation"


def test_real_gate_e2e_fails_closed_without_external_approval():
    channel = ConfirmationChannel()
    registry, calls = _make_registry()
    boundary = ExecutionBoundary(channel, registry)
    gateway = AgencyGateway(channel, make_evaluator())
    decision = gateway.route(_make_real_gate_request())
    assert decision.is_action is True
    assert decision.requires_confirmation is True
    assert decision.confirmation is not None

    result = boundary.execute(
        decision.confirmation, "delete_file", "filesystem", "s1",
        {"path": "file_A.txt"},
    )
    assert result.executed is False
    assert result.reason == "external_approval_unavailable"
    assert calls == []


def test_real_gate_target_bound_path_fails_closed_when_non_atomic(tmp_path):
    path = tmp_path / "file_A.txt"
    path.write_text("data")
    target_ref = TargetRef(str(path))
    channel = ConfirmationChannel()
    registry, calls = _make_registry()
    boundary = ExecutionBoundary(channel, registry, FileSystemTargetAuthority())
    gateway = AgencyGateway(
        channel, make_evaluator(), target_authority=FileSystemTargetAuthority()
    )
    decision = gateway.route(_make_real_gate_request(target_ref=target_ref))
    assert decision.confirmation is not None

    result = boundary.execute(
        decision.confirmation, "delete_file", "filesystem", "s1",
        {"path": "file_A.txt"}, target_ref=target_ref,
    )
    assert result.executed is False
    assert result.reason == "atomic_target_execution_unavailable"
    assert calls == []

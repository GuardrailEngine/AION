"""End-to-end: real AgencyGate.decide -> adapter -> gateway -> boundary -> tool."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.agency.gateway import AgencyGateway
from aion.agency.real_gate_adapter import make_evaluator, map_request_for_real_gate
from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel
from tests.fixtures_core import (
    make_constitution,
    make_critique,
    make_reasoning,
    make_request,
    make_risk,
)


def _make_real_gate_request():
    request = map_request_for_real_gate(
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
        reasoning=make_reasoning(),
        critique=make_critique(),
        risk=make_risk(),
        constitution=make_constitution(),
    )
    request["req"] = make_request()
    return request


def _make_registry():
    reg = ToolRegistry()
    calls = []

    def delete_file(payload):
        calls.append(payload)
        return {"deleted": payload["path"]}

    reg.register("filesystem", delete_file)
    return reg, calls


def test_real_gate_evaluator_returns_tuple():
    """Call real AgencyGate.decide via the adapter with Core objects."""
    evaluator = make_evaluator()
    is_action, reason = evaluator(_make_real_gate_request())
    assert is_action is True
    assert isinstance(reason, str)
    assert reason == "action_requires_confirmation"


def test_real_gate_e2e_full_path():
    """Full path: real gate -> adapter -> gateway -> boundary -> tool."""
    channel = ConfirmationChannel()
    reg, calls = _make_registry()
    boundary = ExecutionBoundary(channel, reg)
    gateway = AgencyGateway(channel, make_evaluator())

    decision = gateway.route(_make_real_gate_request())

    assert decision.is_action is True
    assert decision.requires_confirmation is True
    assert decision.confirmation is not None

    result = boundary.execute(
        event=decision.confirmation,
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
    )
    assert result.executed is True
    assert result.reason == "ok"
    assert calls == [{"path": "file_A.txt"}]

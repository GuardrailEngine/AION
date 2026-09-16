"""Integration tests for the real-gate adapter."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.agency.real_gate_adapter import (
    make_evaluator,
    map_request_for_real_gate,
)


def _common_inputs():
    return {
        "reasoning": None,
        "critique": None,
        "risk": None,
        "constitution": None,
    }


def test_adapter_reports_missing_input():
    """If a required input is missing, adapter refuses to fabricate."""
    evaluator = make_evaluator()
    is_action, reason = evaluator({"action": "x", "tool": "y", "session_id": "s", "payload": {}})
    assert is_action is False
    assert reason.startswith("adapter_missing_input:")


def test_adapter_with_full_inputs_returns_tuple():
    """Incomplete placeholder inputs are rejected without fabrication."""
    evaluator = make_evaluator()
    request = map_request_for_real_gate(
        action="read_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
        **_common_inputs(),
    )
    result = evaluator(request)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert isinstance(result[1], str)


def test_mapped_request_has_gateway_and_gate_fields():
    """The mapped request contains both gateway and real-gate fields."""
    request = map_request_for_real_gate(
        action="delete_file",
        tool="filesystem",
        session_id="s1",
        payload={"path": "file_A.txt"},
        target_version="v1",
        **_common_inputs(),
    )
    for key in ("action", "tool", "session_id", "payload", "target_version",
                "req", "reasoning", "critique", "risk", "constitution"):
        assert key in request, f"missing key: {key}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

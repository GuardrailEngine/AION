"""Integration tests for the real-gate adapter."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from aion.agency.real_gate_adapter import make_evaluator, map_request_for_real_gate
from tests.fixtures_core import (
    make_constitution,
    make_critique,
    make_reasoning,
    make_request,
    make_risk,
)


def _mapped_request(req=None, **overrides):
    values = {
        "action": "delete_file",
        "tool": "filesystem",
        "session_id": "s1",
        "payload": {"path": "file_A.txt"},
        "req": make_request() if req is None else req,
        "reasoning": make_reasoning(),
        "critique": make_critique(),
        "risk": make_risk(),
        "constitution": make_constitution(),
    }
    values.update(overrides)
    return map_request_for_real_gate(**values)


def test_adapter_reports_missing_request_without_fabricating():
    evaluator = make_evaluator()
    assert evaluator({"action": "x", "tool": "y", "session_id": "s", "payload": {}}) == (
        False, "adapter_missing_input:req"
    )


def test_adapter_accepts_canonical_core_objects():
    req = make_request()
    request = _mapped_request(req=req)
    assert request["req"] is req
    assert make_evaluator()(request) == (True, "action_requires_confirmation")


def test_adapter_rejects_wrong_request_type():
    evaluator = make_evaluator()
    request = _mapped_request()
    request["req"] = {"intent": "TASK", "requires_action_verified": True}
    assert evaluator(request) == (False, "adapter_invalid_input:req")
    with pytest.raises(TypeError, match="aion_core.Request"):
        _mapped_request(req={"intent": "TASK"})


def test_mapper_preserves_request_identity_and_gateway_scope():
    req = make_request(request_id="req-bound")
    request = _mapped_request(req=req, target_version="v1", target_hash="h1")
    assert request["req"] is req
    assert request["req"].request_id == "req-bound"
    assert request["action"] == "delete_file"
    assert request["tool"] == "filesystem"
    assert request["session_id"] == "s1"
    assert request["payload"] == {"path": "file_A.txt"}
    assert request["target_version"] == "v1"
    assert request["target_hash"] == "h1"

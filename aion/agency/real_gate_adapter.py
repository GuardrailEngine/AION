"""Adapter wiring AgencyGate from aion_core (1).py into AgencyGateway.

The real AgencyGate exposes .decide(req, reasoning, critique, risk,
constitution). AgencyGateway expects a callable returning
(is_action: bool, reason: str). This adapter bridges them.

The adapter does not fabricate reasoning, critique, risk, constitution,
or request objects. The caller must supply the actual Core-owned values.
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_CORE_PATH = Path(__file__).resolve().parents[2] / "aion_core (1).py"
REQUIRED_INPUTS = ("req", "reasoning", "critique", "risk", "constitution")


def _load_core():
    module_name = "aion_core_available_snapshot"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    if not _CORE_PATH.is_file():
        raise RuntimeError(f"aion_core snapshot not found: {_CORE_PATH}")
    spec = importlib.util.spec_from_file_location(module_name, _CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load aion_core snapshot: {_CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def make_evaluator() -> Callable[[dict], tuple[bool, str]]:
    """Return a callable for AgencyGateway backed by the real AgencyGate."""
    core = _load_core()
    gate = core.AgencyGate()

    def evaluator(request: dict) -> tuple[bool, str]:
        if not isinstance(request, dict):
            return False, "adapter_invalid_request"

        for name in REQUIRED_INPUTS:
            if name not in request or request[name] is None:
                return False, f"adapter_missing_input:{name}"

        decision = gate.decide(
            req=request["req"],
            reasoning=request["reasoning"],
            critique=request["critique"],
            risk=request["risk"],
            constitution=request["constitution"],
        )

        is_action = decision.level == core.AgencyLevel.ACTION
        reason = decision.reason or decision.level.value
        return is_action, str(reason)

    return evaluator


def map_request_for_real_gate(
    action: str,
    tool: str,
    session_id: str,
    payload: Any,
    reasoning: Any,
    critique: Any,
    risk: Any,
    constitution: Any,
    target_version: str | None = None,
) -> dict:
    """Build gateway fields plus caller-supplied real-gate inputs.

    The ``req`` value is intentionally not fabricated or converted. It must
    be a real Request object accepted by the available AgencyGate snapshot.
    """
    return {
        "action": action,
        "tool": tool,
        "session_id": session_id,
        "payload": payload,
        "target_version": target_version,
        "req": {
            "action": action,
            "tool": tool,
            "session_id": session_id,
            "payload": payload,
        },
        "reasoning": reasoning,
        "critique": critique,
        "risk": risk,
        "constitution": constitution,
    }

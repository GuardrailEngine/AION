"""Adapter wiring the real Core AgencyGate into AgencyGateway.

The adapter passes Core-owned objects through unchanged. It does not fabricate
requests or claim that a channel-issued event is external approval.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import aion_core


def _load_core():
    """Return the repository's canonical import-compatible Core module."""
    return aion_core


def make_evaluator() -> Callable[[dict], tuple[bool, str]]:
    """Return a callable backed by AgencyGate and canonical Core types."""
    core = _load_core()
    gate = core.AgencyGate()
    expected_types = {
        "req": core.Request,
        "reasoning": core.Reasoning,
        "critique": core.Critique,
        "risk": core.Risk,
        "constitution": core.ConstitutionResult,
    }

    def evaluator(request: dict) -> tuple[bool, str]:
        if not isinstance(request, dict):
            return False, "adapter_invalid_request"

        for name, expected_type in expected_types.items():
            if name not in request or request[name] is None:
                return False, f"adapter_missing_input:{name}"
            if not isinstance(request[name], expected_type):
                return False, f"adapter_invalid_input:{name}"

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
    *,
    action: str,
    tool: str,
    session_id: str,
    payload: Any,
    req: Any,
    reasoning: Any,
    critique: Any,
    risk: Any,
    constitution: Any,
    target_ref: Any | None = None,
    target_version: str | None = None,
    target_hash: str | None = None,
) -> dict:
    """Build gateway fields while preserving the actual Core Request object.

    ``req`` must be an instance of the canonical ``aion_core.Request`` type.
    No dictionary-shaped substitute is created.
    """
    core = _load_core()
    if not isinstance(req, core.Request):
        raise TypeError("req must be an aion_core.Request instance")

    expected_types = (
        ("reasoning", reasoning, core.Reasoning),
        ("critique", critique, core.Critique),
        ("risk", risk, core.Risk),
        ("constitution", constitution, core.ConstitutionResult),
    )
    for name, value, expected_type in expected_types:
        if not isinstance(value, expected_type):
            raise TypeError(f"{name} must be an aion_core.{expected_type.__name__} instance")

    return {
        "action": action,
        "tool": tool,
        "session_id": session_id,
        "payload": payload,
        "target_ref": target_ref,
        "target_version": target_version,
        "target_hash": target_hash,
        "req": req,
        "reasoning": reasoning,
        "critique": critique,
        "risk": risk,
        "constitution": constitution,
    }

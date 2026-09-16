"""Fixtures for real aion_core objects.

Minimal deterministic values. They satisfy the actual shapes required by
AgencyGate.decide() without modifying the available Core snapshot.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CORE_PATH = Path(__file__).resolve().parents[1] / "aion_core (1).py"
_CORE_MODULE_NAME = "aion_core_available_snapshot"


def _core():
    existing = sys.modules.get(_CORE_MODULE_NAME)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(_CORE_MODULE_NAME, _CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load Core snapshot: {_CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_CORE_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def make_request(
    request_id: str = "req-001",
    raw_input: str = "delete file_A.txt",
    intent=None,
    domain=None,
    intent_confidence: float = 0.9,
    requires_action_proposal: bool = True,
    requires_action_verified: bool = True,
):
    core = _core()
    intent = core.IntentType.TASK if intent is None else intent
    domain = core.Domain.OTHER if domain is None else domain
    return core.Request(
        request_id=request_id,
        raw_input=raw_input,
        intent=intent,
        domain=domain,
        intent_confidence=intent_confidence,
        requires_action_proposal=requires_action_proposal,
        requires_action_verified=requires_action_verified,
    )


def make_reasoning():
    return _core().Reasoning(
        answer="User wants to delete a file.",
        assumptions=[],
        uncertainty=[],
    )


def make_critique():
    return _core().Critique(
        evidence_sufficient=True,
        hidden_assumptions=[],
        false_balance_detected=False,
        could_be_wrong=False,
        over_exercising_authority=False,
        confidence=0.9,
        uncertainty=[],
    )


def make_risk():
    core = _core()
    return core.Risk(
        level=core.RiskLevel.HIGH,
        factors=core.RiskFactors(
            severity=0.8,
            probability=0.9,
            reversibility=0.1,
            affected_parties=1,
        ),
        justification="Destructive action on a user file.",
    )


def make_constitution():
    return _core().ConstitutionResult(
        checks_passed=["no_pii", "user_intent_clear"],
        checks_failed=[],
        checks_clarify=[],
        checks_notice=[],
    )

"""Fixtures built from the repository's canonical aion_core module."""
from __future__ import annotations

import aion_core


def _core():
    return aion_core


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

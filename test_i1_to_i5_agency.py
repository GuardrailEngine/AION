"""
Invariants I-1 إلى I-5 — Agency Gate.
"""
import pytest
from dataclasses import replace
from aion_core import (
    AgencyGate, Request, Reasoning, Critique, Risk, RiskFactors, RiskLevel,
    ConstitutionResult, IntentType, Domain,
    AgencyLevel, ExecutionStatus, DecisionStatus,
)


def _req(intent=IntentType.QUESTION, verified=False, confidence=0.9, text="test"):
    r = Request.new(text, intent, Domain.GENERAL, confidence)
    return replace(r, requires_action_verified=verified)


def _crit(conf=0.9, evidence=True, hidden=None, over_auth=False, false_bal=False):
    return Critique(
        evidence_sufficient=evidence,
        hidden_assumptions=hidden or [],
        over_exercising_authority=over_auth,
        false_balance_detected=false_bal,
        confidence=conf,
    )


def _risk(level, rev=1.0):
    return Risk(level, RiskFactors(0.5, 0.5, rev, 1), "test")


@pytest.fixture
def gate():
    return AgencyGate()


# ─── I-1: كل transition مُسجَّل ───

def test_i1_transitions_audited(gate):
    d = gate.decide(
        _req(IntentType.DECISION_REQUEST), Reasoning(answer="ok"),
        _crit(), _risk(RiskLevel.LOW), ConstitutionResult()
    )
    assert len(d.transitions) >= 1
    for t in d.transitions:
        assert "→" in t and ":" in t


# ─── I-2: ارتفاع الخطر لا يرفع الوكالة ───

def test_i2_high_risk_does_not_increase_agency(gate):
    req = _req(IntentType.QUESTION)
    r = Reasoning(answer="ok")
    c = _crit()
    low = gate.decide(req, r, c, _risk(RiskLevel.LOW), ConstitutionResult())
    high = gate.decide(req, r, c, _risk(RiskLevel.HIGH), ConstitutionResult())
    assert low.level == high.level
    assert high.requires_confirmation is True


# ─── I-3: خرق الدستور → رفض ───

def test_i3_constitution_violation_refuses(gate):
    const = ConstitutionResult(checks_failed=["article_5:false_balance"])
    d = gate.decide(_req(), Reasoning(answer="ok"), _crit(), _risk(RiskLevel.LOW), const)
    assert d.level == AgencyLevel.REFUSAL
    assert d.execution_status == ExecutionStatus.BLOCKED
    assert d.decision_status == DecisionStatus.REFUSED


# ─── I-4: ACTION ≠ EXECUTED ───

def test_i4_action_does_not_mean_executed(gate):
    req = _req(IntentType.TASK, verified=True, text="أرسل البريد")
    d = gate.decide(req, Reasoning(answer="ok"), _crit(), _risk(RiskLevel.LOW), ConstitutionResult())
    if d.level == AgencyLevel.ACTION:
        assert d.execution_status == ExecutionStatus.AWAITING_CONFIRMATION
    assert d.execution_status != ExecutionStatus.EXECUTED


# ─── I-5: لا ACTION بلا verified ───

def test_i5_no_action_without_verified(gate):
    req = _req(IntentType.TASK, verified=False, text="احذف الملفات")
    d = gate.decide(req, Reasoning(answer="ok"), _crit(), _risk(RiskLevel.LOW), ConstitutionResult())
    assert d.level != AgencyLevel.ACTION


# ─── خطر حرج غير قابل للعكس → رفض ───

def test_irreversible_critical_risk_refuses(gate):
    req = _req(IntentType.TASK, verified=True, text="احذف كل شيء")
    d = gate.decide(req, Reasoning(answer="ok"), _crit(),
                    _risk(RiskLevel.CRITICAL, rev=0.1), ConstitutionResult())
    assert d.level == AgencyLevel.REFUSAL
    assert d.execution_status == ExecutionStatus.BLOCKED


# ─── ثقة نية منخفضة → توضيح، لا رفض ───

def test_low_intent_confidence_clarification_not_refusal(gate):
    req = _req(confidence=0.2, text="شيء ما")
    d = gate.decide(req, Reasoning(answer="ok"), _crit(), _risk(RiskLevel.LOW), ConstitutionResult())
    assert d.decision_status == DecisionStatus.CLARIFICATION_REQUIRED
    assert d.level != AgencyLevel.REFUSAL


# ─── M-8: confidence لا يمنع downgrade ───

def test_m8_confidence_alone_does_not_prevent_downgrade(gate):
    """
    critique.confidence=0.99 لكن evidence_sufficient=False.
    الحاجز يُفعَّل → downgrade.
    """
    req = _req(IntentType.TASK, verified=True, text="أرسل البريد")
    c = _crit(conf=0.99, evidence=False)  # حاجز
    d = gate.decide(req, Reasoning(answer="ok"), c, _risk(RiskLevel.LOW), ConstitutionResult())
    # الحاجز خفّض من ACTION إلى RECOMMENDATION
    assert d.level != AgencyLevel.ACTION
    assert any("barrier" in t for t in d.transitions), \
        f"Barrier not recorded in transitions: {d.transitions}"

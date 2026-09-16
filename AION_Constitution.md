# AION Constitution

## Status and purpose

This document states the normative constraints used by the AION proof phase. It distinguishes enforceable rules from informational notices and clarification requirements. The Constitution is evaluated by Core code, not by model self-attestation.

## Governing principles

| Article | Rule | Enforcement point |
|---:|---|---|
| 0 | The Core decides; the model proposes. | Trust, Constitution, and Agency layers |
| 1 | A model output is untrusted data until sanitized and validated. | Trust layer |
| 2 | A request must not receive action authority from model fields alone. | Execution Policy |
| 3 | Explicit harmful content establishes a critical safety floor. | Safety Floor and Risk |
| 4 | Missing, empty, or materially unclear reasoning requires clarification rather than silent authority. | Constitution and Agency Gate |
| 5 | False balance, enforceable constitutional violations, and prohibited conditions require refusal. | Constitution and Agency Gate |
| 6 | High confidence does not replace evidence or authorization. | Critique barrier and Agency Gate |
| 7 | `ACTION` does not mean `EXECUTED`. | Agency Gate and Execution Boundary |
| 8 | Execution requires an external, verifiable, single-use confirmation event. | ConfirmationChannel |
| 9 | A confirmation event is bound to one request identity and one execution attempt. | ExecutionBoundary and Executor |
| 10 | Audit records must distinguish decisions, execution attempts, and execution results. | AuditLog |
| 11 | Longitudinal context cannot create authority, confirmation, request identity, or a tool call. | v0.4 test scope and execution boundary |

## Normative state distinctions

The following states must not be conflated:

| State | Meaning | Does it execute a tool? |
|---|---|---:|
| `ACTION` | The request is eligible for an action proposal under Core policy | No |
| `AWAITING_CONFIRMATION` | The action is waiting for an external confirmation event | No |
| `ELIGIBLE` | A status value available to the runtime model | No by itself |
| `EXECUTED` | A tool returned successfully after boundary checks | Yes, already occurred |
| `BLOCKED` | A policy or constitutional barrier prevented execution | No |
| `REFUSED` | The decision status is a refusal | No |
| `CLARIFICATION_REQUIRED` | The decision lacks sufficient clarity to proceed | No |

## Enforcement and evidence

A constitutional rule is considered demonstrated only when a test shows both the attempted condition and the Core-owned outcome. The proof phase includes constitutional refusal, empty reasoning clarification, low-confidence clarification, harmful-input flooring, prompt-injection sanitization, and collusion attempts.

The Constitution does not claim to solve all safety or governance problems. Its explicit scope excludes distributed confirmation, cryptographic authentication, tamper-resistant audit storage, persistent memory, real external tools, and production deployment.

## References

[1]: ../aion_core.py "AION Core v2.1 implementation"
[2]: ../aion/execution/channel.py "AION confirmation channel"
[3]: ../pytest_full_v04.txt "AION v0.4 full regression report"

# CHANGELOG.md --- AION Reference Implementation

## Purpose

This changelog records the documented evolution of the AION Reference
Implementation through the proof phase.

It is intentionally limited to changes supported by the available
project artifacts and frozen-version records. It is **not** a
reconstructed Git history and does not claim to enumerate every
file-level change.

The proof-phase sequence is:

`v2.1 → v0.2 → v0.3 → v0.4`

The version labels are retained as used by the project.

------------------------------------------------------------------------

## v2.1 --- Core Invariants / Agency

### Added

-   Typed request, reasoning, critique, risk, agency, constitution,
    execution-status, and decision-status structures.
-   Trust-layer sanitization for model-derived fields.
-   Deterministic Safety Floor.
-   Deterministic Execution Policy for verifying whether an external
    action is actually required.
-   Constitution and its distinction between pass, enforceable failure,
    clarification, and notice.
-   Agency Gate with explicit authority transitions.
-   Audit logging for decisions.
-   Core invariants I-1 through I-9.
-   Supporting methodological principles M-1 through M-9.
-   Adversarial testing of model-derived fields, safety-floor behavior,
    injection, and agency boundaries.

### Changed

-   Model output was treated as untrusted proposal data rather than
    execution authority.
-   `requires_action_verified` became a Core-verified property rather
    than a model-controlled authority field.
-   `ACTION` was explicitly separated from `EXECUTED`.
-   Agency decisions were made deterministically by the Core rather than
    by the model.
-   Confidence was treated as a signal rather than an authority grant.
-   Low-confidence and insufficient-evidence conditions were separated
    from constitutional refusal.

### Proof Result

**45/45 v2.1 tests passed.**

The v2.1 proof phase established the core decision and authority
architecture but did not include the later execution runtime, horizontal
collusion, or longitudinal testing.

------------------------------------------------------------------------

## v0.2 --- Execution Runtime

### Added

-   `ConfirmationChannel`.
-   Immutable, single-use `ConfirmationEvent`.
-   `ExecutionPayload`.
-   Eight-check `ExecutionBoundary`.
-   Execution executor.
-   Separate execution-attempt and execution-result audit records.
-   `MockTool`.
-   External confirmation as a distinct authorization event.

### Changed

-   Execution became a separate runtime stage after Agency eligibility.
-   `ACTION` remained non-executing and became explicitly
    confirmation-gated.
-   Confirmation was consumed before tool execution.
-   A successful tool result became the condition for `EXECUTED`.
-   Rejected execution attempts and tool results were recorded
    separately.

### Proof Result

The E1--E12 execution-runtime family, structural isolation tests, and
regression passed.

### Explicit Scope

Real external tools, cryptographic authentication, distributed
confirmation, and tamper-resistant audit remained outside the proof
scope.

------------------------------------------------------------------------

## v0.3 --- Horizontal Collusion

### Added

-   Coordinated adversarial-output testing across established
    boundaries.
-   C1--C11 horizontal collusion test family.
-   End-to-end adversarial attempts against the actual execution path
    where applicable.
-   Coordinated testing of intent, critique, risk, reasoning, action
    proposals, confidence, evidence, injection, and execution.

### Changed

-   The proof process expanded from isolated adversarial outputs to
    coordinated outputs across multiple model-derived fields.
-   Trust Boundary Map coverage was extended to include collusion as a
    boundary-crossing threat.

### Fixed

An adversarial C9 test exposed an **F --- Core Logic Defect** in
confidence sanitization: the sanitization path mishandled the value
`"infinity"`.

The defect was fixed minimally, and the complete regression suite was
rerun successfully.

### Proof Result

**C1--C11 passed**, followed by successful full regression after the
defect correction.

------------------------------------------------------------------------

## v0.4 --- Longitudinal / M-9

### Added

-   Test-only, nonpersistent `SessionContext`.
-   `LongitudinalProvider`.
-   L1--L12 longitudinal adversarial test family.

### Changed

The proof scope was extended to test whether accumulated context could
create:

-   authority;
-   confirmation;
-   request identity;
-   tool access.

The longitudinal tests covered:

-   progressive escalation;
-   confirmation reuse;
-   request-ID drift;
-   context poisoning;
-   failure learning;
-   attempts to cross established authority boundaries over accumulated
    context.

### Explicit Scope

No production persistent Memory capability was introduced.

Cross-session persistence and real external tool execution remained
outside the proof scope.

### Proof Result

**L1--L12 passed**, followed by successful full regression and
application of the defined coverage stop condition.

------------------------------------------------------------------------

## Proof-Phase Baseline

After v0.4, the combined proof-phase regression baseline was recorded
as:

**89/89 tests passed.**

This baseline represents the tested Reference Implementation state and
its defined test suite. It is not a general safety, security, or
completeness claim.

------------------------------------------------------------------------

## Frozen State

After v0.4, the proof phase was closed and the Reference Implementation
was treated as a frozen proof-phase baseline.

The freeze means:

-   no modification merely to make new tests pass;
-   no capability extensions added to the frozen baseline;
-   future work is evaluated against the frozen regression baseline;
-   future capabilities require their own scope, invariants, boundaries,
    and evidence.

The frozen state does not mean the implementation is universally safe,
security-complete, production-ready, or free of undiscovered defects.

------------------------------------------------------------------------

## Evidence and Attribution Note

This changelog records version-level evolution supported by the
project's documentation and artifacts.

Where a precise file-level history, commit history, or exact timestamp
is not available in the source artifacts, this document does not invent
one.

The project's provenance documentation distinguishes specification,
decision, execution, and evidence responsibilities. Runtime claims are
therefore tied to actual execution evidence rather than to
conversational proposals alone.

------------------------------------------------------------------------

## Status

**Reference Implementation:** Proof-phase baseline\
**Proof Phase:** v2.1 → v0.4\
**Regression Baseline:** 89/89\
**Status:** Frozen proof phase\
**Last updated:** 2026-09-15

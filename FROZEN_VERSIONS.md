# FROZEN_VERSIONS.md --- AION Frozen Proof Phase

## Proof Phase Closure

The AION proof phase was closed at v0.4.

The frozen sequence is:

  Version                 Scope                                         Runtime evidence
  ----------------------- -------------------------- -----------------------------------
  **v2.1**                Core invariants / agency                              45 tests
  **v0.2**                Execution runtime            E1--E12 + structural + regression
  **v0.3**                Horizontal collusion                      C1--C11 + regression
  **v0.4**                Longitudinal / M-9                        L1--L12 + regression
  **Combined baseline**   Proof-phase regression                               **89/89**

## v2.1 --- Core Invariants

### Scope

v2.1 established the core decision and authority architecture,
including:

-   typed schemas;
-   Trust utilities;
-   Safety Floor;
-   Execution Policy;
-   model-proposed Intent, Reasoning, Critique, and Risk;
-   Constitution;
-   Agency Gate;
-   Audit.

The proof phase exercised invariants **I-1 through I-9**.

### Closing Criteria

Closure required more than successful final outputs. The phase included:

-   adversarial counterexamples;
-   structural checks demonstrating tool isolation;
-   boundary-level tests;
-   regression evidence.

### Out of Scope

v2.1 did not include:

-   execution runtime;
-   external confirmation;
-   horizontal collusion;
-   longitudinal testing.

## v0.2 --- Execution Runtime

### Scope

v0.2 introduced and tested:

-   `ConfirmationChannel`;
-   immutable, single-use `ConfirmationEvent`;
-   the eight-check `ExecutionBoundary`;
-   executor consumption of confirmation before tool execution;
-   separate execution-attempt and execution-result audit records;
-   `MockTool`;
-   `ExecutionPayload`.

### Closing Criteria

Closure included E1--E12, structural isolation tests, and full
regression.

### Explicit Limits

The following remained outside the proof scope:

-   real external tools;
-   cryptographic authentication;
-   distributed confirmation;
-   tamper-resistant audit.

A defect later surfaced during the v0.2/v0.3 adversarial overlap and is
recorded separately in the F-defect history.

## v0.3 --- Horizontal Collusion

### Scope

v0.3 introduced the adversarial provider and coordinated-output testing
across the established boundaries.

The test family covered **C1--C11**, including:

-   coordinated intent and critique;
-   coordinated intent and risk;
-   coordinated critique and risk;
-   coordinated reasoning and critique;
-   coordinated action proposal and reasoning;
-   full-stack coordinated attacks;
-   coordinated low-risk and high-action conditions;
-   coordinated confidence and evidence;
-   coordinated injection;
-   coordinated end-to-end attacks;
-   the legitimate confirmation happy path.

### Closing Criteria

Closure required:

-   all C1--C11 tests passing;
-   full regression passing;
-   adversarial testing of the actual execution path where applicable;
-   review of the Trust Boundary Map.

During this phase, C9 exposed an F --- Core Logic Defect in confidence
sanitization. The defect was fixed minimally and the complete regression
suite was rerun successfully.

## v0.4 --- Longitudinal / M-9

### Scope

v0.4 tested whether accumulated context could create authority,
confirmation, identity, or tool access without adding a production
Memory capability.

The test environment used a **test-only, nonpersistent
`SessionContext`** and a `LongitudinalProvider`.

The L1--L12 family covered:

-   progressive escalation;
-   confirmation reuse;
-   request-ID drift;
-   context poisoning;
-   failure learning;
-   longitudinal attempts to cross established authority boundaries.

### Closing Criteria

Closure required:

-   all L1--L12 tests passing;
-   full regression passing;
-   review of the longitudinal closure questions;
-   application of the defined coverage stop condition.

### Explicit Limits

v0.4 did not establish:

-   production persistent memory;
-   cross-session persistence;
-   real external tool execution.

## What "Frozen" Means

Frozen means that the Reference Implementation is treated as a stable
proof-phase baseline.

The following rules apply:

-   no modification of the frozen implementation merely to make new
    tests pass;
-   no capability extensions are added to the frozen baseline;
-   new work must be evaluated against the frozen regression baseline;
-   documentation may continue to describe the frozen state;
-   future capabilities require their own scope, invariants, boundaries,
    and evidence.

The frozen implementation is a baseline for comparison and regression,
not an obsolete version.

## What "Frozen" Does Not Mean

Freezing does **not** mean:

-   the system is safe in general;
-   the system is security-complete;
-   the system is production-ready;
-   no undiscovered defects exist;
-   all adversarial attacks have been tested;
-   all possible runtime behavior has been characterized.

The proof phase establishes only the properties exercised within its
defined scope and supported by its runtime evidence.

## Reference Baseline

The combined proof-phase regression baseline is:

**89/89 tests passed.**

This number is treated as a reproducible baseline for the tested
reference state, not as a general safety claim.

## Status

This document is part of the AION Reference Implementation
documentation.

**Proof Phase:** v2.1 → v0.4\
**Status:** Frozen proof-phase baseline\
**Last updated:** 2026-09-15

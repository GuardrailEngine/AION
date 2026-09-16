# KNOWN_LIMITATIONS.md --- AION Proof-Phase Boundaries

## Purpose

This document records the boundaries of the AION proof phase.

It is not an apology or a general safety disclaimer. It distinguishes
what was proven by runtime evidence from what was implemented but not
exercised, deliberately excluded, or left unknown.

The purpose is to prevent the Reference Implementation from making
claims broader than the evidence supports.

## Evidence Categories

  -----------------------------------------------------------------------
  Category                            Meaning
  ----------------------------------- -----------------------------------
  **Proven**                          Runtime-tested and supported by the
                                      corresponding regression evidence

  **Not Proven**                      Implemented or structurally
                                      present, but not sufficiently
                                      exercised by runtime evidence

  **Out of Scope**                    Deliberately excluded from the
                                      proof phase

  **Unknown**                         Not addressed by the proof phase
  -----------------------------------------------------------------------

No item in this document should be interpreted as "safe," "secure," or
"complete" merely because it appears in a particular category.

## Proven Boundaries

The proof phase established runtime evidence for the following
boundaries:

1.  **LLM output → execution verification**
2.  **Critique confidence → Agency**
3.  **Safety Floor → Risk**
4.  **Constitution → Agency**
5.  **Agency → execution eligibility**
6.  **LLM output → schema boundary**
7.  **Clarification → refusal**
8.  **Confirmation → execution**
9.  **Collusion → boundaries**
10. **Longitudinal state → boundaries**

These are evidence-backed within the tested Reference Implementation
scope. They are not claims of general security or exhaustive coverage.

## Not Proven

The following areas are implemented or structurally present but were not
sufficiently exercised to establish a runtime proof:

-   `ConfirmationChannel._sign` under adversarial access to the shared
    secret;
-   `AuditLog` behavior under external filesystem modification;
-   all syntactically valid but semantically inconsistent combinations
    of execution events and payloads.

These items remain outside the proven boundary set.

## Out of Scope

The following were deliberately excluded from the proof phase:

-   distributed confirmation;
-   cryptographic authentication;
-   tamper-resistant audit;
-   persistent memory;
-   real external tools;
-   production deployment.

In particular, the confirmation mechanism should not be interpreted as
cryptographic authentication. The proof phase did not establish security
properties equivalent to HMAC, PKI, or other cryptographic
authentication systems.

Likewise, the audit implementation is an application-level append-only
record, not a tamper-resistant or independently trusted audit system.

## Unknown

The following remain explicitly unknown:

-   completeness of the deterministic safety floor;
-   future adversarial families not represented in the tested suite;
-   behavior under future model/provider evolution.

The absence of a discovered failure in these areas is not evidence of
completeness.

## 89/89 Baseline

The proof phase produced an **89/89 regression baseline**.

This establishes the recorded result for the tested Reference
Implementation and its defined test suite.

It does not establish:

-   general system safety;
-   security completeness;
-   absence of undiscovered defects;
-   exhaustive adversarial coverage;
-   correctness outside the tested conditions;
-   production readiness.

The baseline is therefore treated as evidence for the tested state, not
as a universal safety metric.

## Constitution and Scope

The limitations above are consistent with the AION Constitution.

The Constitution defines operational constraints and distinguishes
enforceable failures, clarification states, notices, and ordinary
passing conditions. It does not by itself solve every safety,
governance, authentication, memory, or deployment problem.

The proof phase therefore records both constitutional enforcement and
the limits of what that enforcement demonstrates.

## Reference Implementation Boundary

The Reference Implementation is a proof-phase baseline.

Its evidence should be interpreted as:

> **what was tested, what was observed, and what was supported by the
> corresponding artifacts.**

It should not be interpreted as:

> **everything the system can safely do.**

Future capabilities require new scope, new invariants where necessary,
new boundaries, and new runtime evidence.

## Status

This document is part of the AION Reference Implementation
documentation.

**Proof Phase:** v2.1 → v0.4\
**Status:** Proof-phase limitations\
**Last updated:** 2026-09-15

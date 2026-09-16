# ORIGIN.md --- Provenance of the AION Reference Implementation

## Purpose

This document records the provenance of the AION Reference
Implementation.

AION was not produced as the output of a single undifferentiated system
or a single authoring process. It emerged through structured
collaboration in which specification, review, execution, and decision
responsibility were kept distinct.

The purpose of this document is to preserve that distinction and prevent
two common false inferences:

1.  that one AI system authored and validated the entire project;
2.  that architectural specifications or conversational proposals are
    themselves runtime evidence.

## Construction Model

  -----------------------------------------------------------------------
  Responsibility                      Contribution
  ----------------------------------- -----------------------------------
  **Decision**                        Human: scope, phase transitions,
                                      final approval, and verification
                                      claims

  **Specification**                   DeepSeek + ChatGPT: architecture,
                                      invariants, constitutional rules,
                                      and adversarial design

  **Execution**                       Manus: file creation/modification,
                                      pytest execution, and runtime
                                      evidence collection

  **Evidence**                        Manus + Human: pytest output,
                                      transcripts, and reports
  -----------------------------------------------------------------------

The construction model was iterative. The human decision-maker directed
the project scope, defined proof questions, determined phase
transitions, reviewed results, and decided when a phase could be closed.

Conversational AI systems contributed architectural and testing
specifications. The execution environment created and modified
repository artifacts, ran tests, and surfaced runtime results.

## Human Contributions

The human decision-maker directed and approved the proof process,
including:

-   defining the scope of v2.1 through v0.4;
-   determining phase closure criteria;
-   rejecting closures unsupported by evidence;
-   requiring that tests demonstrate the invariants they claim to test;
-   avoiding forced test passes;
-   defining the longitudinal testing family;
-   maintaining separation between agency, execution, confirmation, and
    model output;
-   requiring explicit documentation of limitations;
-   reviewing and approving the interpretation of runtime evidence.

## Specification Contributions

The conversational specification process established and refined:

-   the layered AION architecture;
-   invariants I-1 through I-9;
-   methodological principles M-1 through M-9;
-   constitutional rules and enforcement distinctions;
-   adversarial test families;
-   execution and confirmation boundaries;
-   the Trust Boundary Map;
-   the distinction between proposal, authority, execution eligibility,
    and execution.

These specifications are design artifacts. They are not, by themselves,
evidence that the corresponding properties hold at runtime.

## Execution Contributions

The execution environment was responsible for repository-level
implementation and verification activities, including:

-   creating and modifying project files;
-   executing pytest suites;
-   collecting runtime outputs;
-   preserving test artifacts;
-   surfacing the C9 sanitization defect;
-   applying the minimal correction;
-   rerunning regression tests after the correction.

No production logic was intentionally modified merely to force a test
suite to pass.

## Evidence Boundary

AION distinguishes between specification artifacts and runtime evidence.

  -----------------------------------------------------------------------
  Artifact / Material                 Evidentiary status
  ----------------------------------- -----------------------------------
  Invariant definitions               Specification

  Constitution definitions            Specification

  Architecture diagrams               Specification / conceptual
                                      representation

  Test source files                   Test specification / implementation

  Pytest output                       Runtime evidence

  89/89 regression result             Runtime evidence for the tested
                                      baseline

  Trust Boundary Map                  Evidence-backed only where tied to
                                      corresponding runtime tests and
                                      results
  -----------------------------------------------------------------------

A textual instruction to execute a command is not evidence that the
command was executed.

Repository state and recorded command output are evidence of execution.

Likewise, a proposed test or expected result is not evidence that the
test actually passed.

## Limits of Attribution

This document does not claim that:

-   a single AI system authored or validated the complete
    implementation;
-   every conceptual idea originated from one contributor;
-   conversational specification material independently executed against
    the repository;
-   execution artifacts independently designed the invariants;
-   the human decision-maker personally wrote every implementation file
    or test.

The claim is narrower and more precise:

**AION was constructed through structured collaboration with distinct
responsibilities for decision, specification, execution, and evidence.**

## Why This Document Exists

Provenance matters because the AION proof phase makes claims about
runtime behavior.

Those claims must remain distinguishable from:

-   conceptual proposals;
-   architectural descriptions;
-   expected outcomes;
-   test intentions;
-   conversational reasoning.

The Reference Implementation therefore records not only what was
designed, but also the boundary between what was proposed and what was
actually executed and observed.

## Status

This document is part of the AION Reference Implementation
documentation.

**Proof Phase:** v2.1 → v0.4\
**Documentation status:** Protection layer\
**Last updated:** 2026-09-15

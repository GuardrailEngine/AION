# EXTERNAL_SIGNALS.md --- AION Post-Publication Signal Handling

## Purpose

This document defines how AION treats signals that originate outside the
Reference Implementation, including public reactions, comments,
questions, criticism, and other external feedback.

The purpose is to prevent external reaction from being confused with
runtime evidence or being allowed to directly alter the Reference
Implementation.

This extends the project's evidence discipline into the post-publication
phase.

## Core Principle

> **Public reaction is feedback, not evidence.**

An external reaction may be useful, important, or technically
sophisticated. It is still not, by itself, evidence that an AION
invariant holds or fails.

External signals must pass through an evidence-producing process before
they can justify a change to the implementation or to a project claim.

## Signal-to-Evidence Chain

The intended progression is:

``` text
Public reaction
      ↓
Signal
      ↓
Question / hypothesis
      ↓
Artifact / test
      ↓
Evidence
      ↓
Possible change
```

Each transition has a distinct meaning.

### Reaction

A reaction is an externally expressed response to the public project.

Examples include:

-   agreement;
-   disagreement;
-   criticism;
-   questions;
-   requests for clarification;
-   proposed failure modes;
-   requests for implementation details.

A reaction is not automatically a technical finding.

### Signal

A reaction becomes a signal when it identifies something potentially
worth investigating.

For example:

> "The tests may not cover failures at the seams between components."

This is a signal about a possible coverage gap.

### Question / Hypothesis

The signal is converted into a testable question or hypothesis.

Example:

> "Can an interaction between two already-tested boundaries produce an
> authority transition that neither boundary test detects
> independently?"

The question must be precise enough to determine what evidence would
support or reject it.

### Artifact / Test

The question is translated into an artifact or test where appropriate.

Possible artifacts include:

-   an existing test result;
-   a new adversarial test;
-   a boundary-level test;
-   a runtime trace;
-   a reproducible failure;
-   a source-level inspection where structural evidence is appropriate.

### Evidence

Only an observed and reproducible result can establish runtime evidence.

A claim should not be upgraded merely because:

-   multiple people agree with it;
-   an expert suggested it;
-   it sounds plausible;
-   it contradicts an expected design property;
-   a public discussion becomes highly active.

### Possible Change

A change may be considered only after evidence demonstrates that the
current implementation, test coverage, documentation, or claim needs
revision.

The change itself remains subject to the project's existing invariants,
review process, and regression baseline.

## What External Signals Can Change

External signals may influence:

-   questions investigated in future testing;
-   adversarial test hypotheses;
-   documentation clarifications;
-   known-limitations entries;
-   prioritization of evidence collection;
-   future capability design.

They do not directly authorize:

-   changing a frozen invariant;
-   changing a constitutional rule;
-   raising a safety claim;
-   lowering a limitation;
-   modifying the Reference Implementation merely to satisfy criticism;
-   declaring a boundary proven without new evidence.

## What External Signals Cannot Prove

The following are not sufficient evidence by themselves:

-   a positive comment;
-   a negative comment;
-   a high number of reactions;
-   expert agreement;
-   expert disagreement;
-   apparent community consensus;
-   successful reproduction by an unverified description;
-   claims that a test "should" fail;
-   claims that a test "should" pass.

These may be useful inputs to investigation, but they remain signals
until converted into evidence.

## Relation to M-7

M-7 establishes that boundaries require evidence.

The post-publication extension is:

> **External reaction cannot replace evidence, and external reaction
> cannot by itself change an evidence-backed claim.**

This does not mean external criticism is ignored.

It means criticism is treated as an input to the same disciplined
process used elsewhere in AION:

``` text
Signal
  ↓
Hypothesis
  ↓
Test
  ↓
Runtime evidence
  ↓
Review
  ↓
Possible change
```

## Relation to the Frozen Reference Implementation

The frozen Reference Implementation is not modified because of public
pressure, praise, or criticism.

If an external signal identifies a credible new failure mode, the
appropriate response is to:

1.  record the signal;
2.  formulate a precise hypothesis;
3.  determine whether the frozen baseline already covers it;
4.  create a separate test or artifact when necessary;
5.  collect runtime evidence;
6.  review whether the result affects an invariant, boundary,
    limitation, or documented claim;
7.  decide whether a future implementation change is justified.

The frozen baseline therefore remains a stable comparison point while
new evidence is investigated.

## Example: Boundary-Seam Criticism

A public comment may argue that failures are likely to occur at the
seams between independently tested components.

The correct interpretation is not:

> "The architecture is broken."

Nor is it:

> "The existing 89/89 baseline proves the seams are safe."

The correct interpretation is:

> "This is a testable hypothesis about coverage between boundaries."

The resulting investigation should determine whether the proposed seam
represents:

-   an already-proven boundary;
-   a known limitation;
-   a genuinely untested interaction;
-   or a new failure mode.

Only the resulting evidence can determine whether the Reference
Implementation or its claims require change.

## Public Communication

When responding publicly to technical criticism, the project should
distinguish:

-   what has actually been tested;
-   what the current baseline establishes;
-   what remains unknown;
-   what has become a new test question.

The preferred posture is neither defensive nor submissive.

A useful response pattern is:

> **Acknowledge the signal → state the evidence boundary → convert the
> criticism into a testable question.**

The objective is not to win an argument. It is to improve the quality of
evidence.

## Non-Commitment Rule

Public discussion does not create a project obligation to:

-   publish the repository immediately;
-   disclose internal implementation details;
-   implement a suggested feature;
-   accept an interpretation of the architecture;
-   promise a testing timeline;
-   modify the frozen baseline.

External signals may influence investigation without controlling project
decisions.

## Status

This document records the AION post-publication methodology for handling
external signals.

**Reference Implementation:** Proof-phase baseline\
**Proof Phase:** v2.1 → v0.4\
**Regression Baseline:** 89/89\
**Capability Phase:** Not started\
**Last updated:** 2026-09-15

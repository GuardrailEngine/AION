# AION

Safety decision system with a scoped confirmation channel.

[![AION Tests](https://github.com/GuardrailEngine/AION/actions/workflows/aion-tests.yml/badge.svg)](https://github.com/GuardrailEngine/AION/actions/workflows/aion-tests.yml)

## What it is

AION separates proposal from policy decision and tool dispatch. Core can decide that an action requires confirmation, and the gateway can issue a channel-scoped request event. That event is not evidence that an external user approved the action.

## Current execution status

The reference execution boundary intentionally fails closed. This repository does not currently provide a trusted external-approval verifier, so unbound tool requests are rejected with `external_approval_unavailable`. It also has no atomic compare-and-execute contract for target-bound tools, so target-bound requests are rejected with `atomic_target_execution_unavailable` even when the identity, version, and content hash match.

The channel accepts only the exact event object it issued and can verify and consume that event once under a lock. These checks establish channel provenance and one-shot scope validation only; they do not authenticate an external approval. Do not call tools around the boundary or treat a returned event as approval.

The filesystem authority supplies snapshots. A snapshot is not an atomic filesystem operation and does not close the TOCTOU interval for arbitrary handlers. No target-bound action is dispatched through the current boundary.

## Core adapter

`aion.agency.real_gate_adapter` passes the canonical `aion_core.Request` and related Core objects through unchanged. It rejects dictionary-shaped substitutes rather than fabricating a Core request.

## Development checks

Run the local suite and configured checks with:

```sh
python -m pytest -q
make ci
```

CI tests Python 3.10, 3.11, and 3.12. Coverage and Bandit results describe the tested repository state only; they do not establish absence of vulnerabilities or production readiness.

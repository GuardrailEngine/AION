# AION

Safety decision system with a scoped confirmation channel.

[![AION Tests](https://github.com/GuardrailEngine/AION/actions/workflows/aion-tests.yml/badge.svg)](https://github.com/GuardrailEngine/AION/actions/workflows/aion-tests.yml)

## What it is

AION separates proposal from policy decision and tool dispatch. The gateway can issue a channel-scoped `ConfirmationEvent`; that event records request context but is not evidence that an external user approved the action.

## Current execution status

The default `ExecutionBoundary` remains fail-closed. Unbound actions without a trusted approval verifier return `external_approval_unavailable`. Filesystem and other generic target-bound requests return `atomic_target_execution_unavailable`; a filesystem snapshot is not atomic with a handler call. Unsupported requests never invoke a registered tool handler.

There is one deliberately narrow **test-only** path: an explicitly injected `LocalTestApprovalProvider` plus `SqliteTargetProvider`, with `AION_ENV=test`. It supports only `update_resource` / `sqlite_target`, updating one row identified by a stable `database_id + resource_id`, with a JSON payload shaped exactly as `{"value": ...}`. The signed test receipt binds `aion.confirmation_event_id`, action, tool, session, payload digest, target identity, generation, version, hash, expiry, and a one-time `jti`.

The test provider creates a temporary in-memory HMAC key and keeps its one-time-token ledger in a SQLite database separate from the target database. The target update, target-side `jti` consumption, and `request_id` idempotency record are protected by one `BEGIN IMMEDIATE` transaction. A persistent generation high-water mark prevents delete/recreate ABA reuse. This is test scaffolding, not a real approval authority or a production credential: it does not establish user identity or intent. **Production remains unavailable** until a real independent approval authority and pinned public verification key are integrated.

The channel accepts only the exact event object it issued. Its provenance and one-shot checks do not replace the signed receipt. Do not call tools around the boundary or treat a returned event as approval.

## Core adapter

`aion.agency.real_gate_adapter` passes the canonical `aion_core.Request` and related Core objects through unchanged. It rejects dictionary-shaped substitutes rather than fabricating a Core request.

## Development checks

Run the local suite and configured checks with:

```sh
python -m pytest -q
make ci
```

Coverage and Bandit results describe the tested repository state only; they do not establish absence of vulnerabilities or production readiness.

# AION

Safety decision system with a scoped confirmation channel.

[![AION Tests](https://github.com/GuardrailEngine/AION/actions/workflows/aion-tests.yml/badge.svg)](https://github.com/GuardrailEngine/AION/actions/workflows/aion-tests.yml)

## What it is

AION separates proposal from policy decision and tool dispatch. The gateway can issue a channel-scoped `ConfirmationEvent`; that event records request context but is not evidence that an external user approved the action.

## Current execution status

The default `ExecutionBoundary` remains fail-closed. Unbound actions without a trusted approval verifier return `external_approval_unavailable`. Filesystem and other generic target-bound requests return `atomic_target_execution_unavailable`; a filesystem snapshot is not atomic with a handler call. Unsupported requests never invoke a registered tool handler.

There is one deliberately narrow **test-only** path: an explicitly injected `LocalTestApprovalProvider` plus `SqliteTargetProvider`, with `AION_ENV=test`. It supports only `update_resource` / `sqlite_target`, and updates one pre-existing row using a JSON payload shaped exactly as `{"value": ...}`. The target reference contains the stored `database_id`, resource ID, and file `st_dev`/`st_ino`; the confirmation event and signed receipt bind the resource snapshot's generation, version, and content hash. The receipt additionally binds `aion.confirmation_event_id`, action, tool, session, payload digest, expiry, and a one-time `jti`.

The test provider creates a temporary in-memory HMAC key and keeps its one-time-token ledger in a SQLite database separate from the target database. While the target's `BEGIN IMMEDIATE` transaction is open, the approval-side `jti` is consumed in its own transaction before the target row is changed. The row update, target-side `jti` record, and `request_id` idempotency record commit together in the target transaction. A persistent generation high-water mark prevents delete/recreate ABA reuse. This is test scaffolding, not a real approval authority or a production credential: it does not establish user identity or intent. **Production remains unavailable** until a real independent approval authority and pinned public verification key are integrated.

The channel accepts only the exact event object it issued. Its provenance and one-shot checks do not replace the signed receipt. Do not call tools around the boundary or treat a returned event as approval.

## Test-only SQLite path

The simulator creates a receipt in-process; it does not display an approval prompt, authenticate a person, or prove user intent. Its HMAC key is generated in memory for that provider instance and is not a production signing key. The path is enabled only when `AION_ENV=test` and both test providers are explicitly injected. It updates only one pre-existing `aion_resources` row using `update_resource` / `sqlite_target`; the JSON payload must contain exactly one key, `value`. It exposes no create/delete or generic SQL operation. Tests seed rows directly before calling the boundary. The path does not call a registered tool handler.

The target reference binds the stored database ID, resource ID, and file `st_dev`/`st_ino`; generation, version, and content hash are bound separately in the event and receipt. A regular file copy gets a different file identity and invalidates old references. A hard link shares the same inode and is treated as the same underlying file, not as an independent clone. Device and inode values are operating-system file identifiers, not cryptographic or permanently unique identifiers; inode-number reuse after deletion is outside this test path's guarantee. The target provider binds SQLite through `/proc/self/fd` and checks the opened database path. It refuses initialization when `/proc/self/fd` is unavailable; there is no fallback to a path-only connection. The tests for copied files, hard-link separation between target and approval stores, and symlink repointing were run on Linux x86_64; other operating systems and filesystems have not been validated.

The approval-token ledger and target are separate SQLite databases, so there is no distributed transaction between them. If the target transaction fails after the approval-side `jti` is consumed, that approval remains spent and a fresh approval is needed. If the target transaction commits but its response is lost, a retry with the same request ID and receipt returns the saved result without applying the update again only while the same channel-issued event and test-provider instance (and its in-memory HMAC key) remain available. A process restart loses that in-memory state, so old receipts cannot be replayed to recover the result. This does not provide exactly-once behavior across independent databases.

For the behavior exercised by tests, see `tests/test_sqlite_approval_boundary.py`. These tests cover a test receipt and this single SQLite operation only; they do not validate a production approval service or authorize other target types.

## Core adapter

`aion.agency.real_gate_adapter` passes the canonical `aion_core.Request` and related Core objects through unchanged. It rejects dictionary-shaped substitutes rather than fabricating a Core request.

## Development checks

Run the local suite and configured checks with:

```sh
python -m pytest -q
make ci
```

Coverage and Bandit results describe the tested repository state only; they do not establish absence of vulnerabilities or production readiness.

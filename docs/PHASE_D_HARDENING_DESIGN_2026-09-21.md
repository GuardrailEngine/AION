# Phase D — AION Architecture Hardening Design

**Status:** Design only. No production code, tests, dependencies, CI, or Makefile were changed in this phase.

This document defines an implementation design for the structural gaps established by the Phase A, Phase B, and Phase C evidence. It distinguishes current evidence from proposed enforcement. Proposed behavior is not implemented by this document.

## 1. Evidence Baseline

The current package provides runtime evidence for selected AgencyGate decisions, confirmation scope checks, payload hashing, non-concurrent single-use behavior, local tool dispatch, dictionary-based field tracing, and process-local audit records. The current package also provides direct evidence that `HIGH` binding drift is recorded but does not block execution.

The Phase B and Phase C tests establish the following boundaries:

- `ConfirmationChannel` can compare a confirmation with current target version and target hash when those current values are supplied directly to the channel.
- `ExecutionBoundary.execute()` does not receive current target values. Execution-time target binding is therefore **not established**.
- A forced thread interleaving allows two calls to `verify_and_consume()` to return success for one confirmation. This demonstrates a non-atomic current seam for that schedule; it does not establish behavior for every race or for multiple processes.
- `ConfirmationEvent` is mutable. Changing its identity and binding fields changes the values used by verification.
- `ConfirmationChannel` checks `action` and `tool`, while `ToolRegistry` resolves a handler by tool name only.
- `dict` payloads are wrapped in `TracingRow`. A non-dict `Mapping` is outside the current boundary tracing branch.
- Channel audit records are process-local and can be modified through the shallow records returned by `audit_log()`.
- `Pipeline.process()` returns a `Decision`; it does not automatically create a confirmation-to-boundary-to-tool path. `execute_decision()` is currently disabled.

These observations are evidence about the current reference implementation. They are not claims that the current seams are exploitable in every deployment.

## 2. Target Binding Design

### Current gap

Target binding is available at `ConfirmationChannel.verify()` but is not part of the `ExecutionBoundary.execute()` contract. A confirmation can contain `target_version` and `target_hash` while the actual execution call provides no authoritative current target state. The execution boundary therefore cannot establish that the target used by the tool is the target approved by the confirmation.

### Proposed invariant

> A tool may execute only when the confirmation scope, payload binding, and authoritative target state all match at the final execution boundary.

The invariant has two separate requirements. First, the confirmation must capture the target state that was approved. Second, the boundary must obtain and validate the target state that will actually be used by the tool immediately before dispatch.

### Data flow

1. The target resolver obtains a canonical target snapshot before confirmation issuance. The snapshot contains a stable target identifier, a version when the target system provides one, and a canonical target representation.
2. The target binder computes `target_hash` from that canonical representation. The issuer stores `target_version` and `target_hash` in the confirmation event.
3. Human confirmation authorizes the event scope. Human confirmation does not replace target verification.
4. The execution boundary obtains a fresh target snapshot through a target resolver selected for the action and target.
5. The boundary passes the fresh version and hash to the channel's atomic consume operation together with action, tool, session, request identity, and payload hash.
6. The boundary gives the tool the same target snapshot or a target handle whose identity is tied to the validated snapshot. It must not re-resolve a different target after validation.

### API changes

A compatible design should introduce explicit types rather than passing unrelated optional strings throughout the call chain:

```python
@dataclass(frozen=True)
class TargetSnapshot:
    target_id: str
    version: str | None
    content_hash: str

@dataclass(frozen=True)
class TargetBinding:
    target_id: str
    version: str | None
    content_hash: str
```

The proposed boundary shape is conceptually:

```python
ExecutionBoundary.execute(
    event,
    action,
    tool,
    session_id,
    payload,
    *,
    request_id,
    target_snapshot: TargetSnapshot,
) -> ExecutionResult
```

A target resolver may instead be owned by the boundary:

```python
ExecutionBoundary.execute(
    event,
    action,
    tool,
    session_id,
    payload,
    *,
    request_id,
    target_resolver,
)
```

The resolver form is safer when callers cannot be trusted to supply a stale snapshot, but it requires an explicit action-to-target capability contract. **DESIGN DECISION:** choose between boundary-owned resolution and caller-supplied snapshots only after the target model and tool contract are defined.

The channel should compare `event.target_id`, `event.target_version`, and `event.target_hash` against the authoritative execution snapshot. A target identifier is needed because a version and hash alone do not state which object is being checked.

### Failure semantics

- Missing target state for an action that declares target binding: refuse before handler invocation with a distinct `target_state_missing` reason.
- Missing target state for an action explicitly declared target-free: allow only if the action contract says that no target binding is applicable.
- Version mismatch: refuse with `target_drift`.
- Hash mismatch: refuse with `target_hash_mismatch`.
- Target identifier mismatch: refuse with `target_identity_mismatch`.
- Malformed or non-canonical target representation: refuse with `target_state_invalid`.
- Resolver failure or timeout: do not convert the failure into an unbound execution. The action remains unexecuted and the failure is audited.

The system should distinguish a missing target from a changed target. Treating both as a generic success would violate the proposed invariant.

### Version and hash semantics

The version is an optimistic concurrency token supplied by the target system. The hash is a content or relevant-field digest computed from a canonical representation. The version detects ordinary state changes when the target system guarantees monotonic versioning. The hash detects content changes and closes the version-only ABA case when the hash covers the relevant target state.

Both should remain required for actions that are target-bound. A version without a hash permits ABA when a target returns to an earlier version. A hash without a target identifier risks comparing the right content from the wrong object. A target-free action should declare that status explicitly rather than relying on omitted optional values.

### TOCTOU model

The target snapshot used for validation must be the same snapshot used by the tool. Reading a target, validating it, and then allowing the tool to look it up again creates a new time-of-check/time-of-use gap. The tool contract should receive a validated target handle or immutable snapshot. If the external target system supports a compare-and-swap operation, the tool should perform the side effect under that same version/hash precondition.

### Compatibility impact

Making target binding mandatory for all existing actions would be a breaking change. A staged compatibility mode can preserve target-free actions while requiring explicit action metadata:

- `TARGET_BOUND`: target snapshot required; missing state refuses.
- `TARGET_FREE`: no target snapshot is permitted or needed.
- `LEGACY_UNDECLARED`: accepted only during migration, emits a high-signal audit record, and is excluded from hardened execution.

**DESIGN DECISION:** determine whether legacy undeclared actions may execute temporarily. The evidence establishes that silent omission is unsafe for target-bound actions, but it does not define the inventory of target-free actions.

## 3. Atomic Confirmation Design

### State machine

The confirmation state machine should be explicit:

```text
issued / unused
      │
      ├── valid atomic consume ──> consumed
      │                              │
      │                              └── all later attempts -> already_used
      ├── expired or scope mismatch -> unused + rejected attempt audit
      └── malformed/revoked         -> unused + rejected attempt audit
```

A failed verification must not consume the event. A successful consume must transition from `unused` to `consumed` as one authoritative operation.

### Synchronization boundary

The atomic operation must include all checks that determine eligibility and the state transition:

```text
lookup event identity
→ verify not consumed
→ verify expiry and scope
→ verify payload and target binding
→ atomically mark consumed
→ append outcome
```

A Python `Lock` can protect this operation within one process, but it does not protect multiple workers or processes. The authoritative storage boundary must therefore be chosen explicitly.

For a single-process deployment, a channel-owned lock around the event table is sufficient for thread safety. For multiple processes, the authoritative state must be in a transactional store that supports conditional update, such as a database row with `UPDATE ... WHERE state = 'unused'`, or a service with an atomic compare-and-set primitive. For distributed execution, the store must define transaction durability, ownership, clock behavior, and failure recovery.

**DESIGN DECISION:** select the authoritative store. The current in-memory dictionary is not sufficient for process or distributed single-use guarantees.

### Concurrency semantics

Exactly one consumer may receive `consumed/ok`. Every other consumer must receive `already_used` or a more specific refusal. A second consumer must never invoke the tool. The consume result must carry the event identity used for the winning transition.

### Process and distributed considerations

Thread safety and distributed safety are separate claims. A process-local lock cannot establish cross-process exclusivity. A database transaction can establish exclusivity only within the database's durability and availability model. A distributed lease introduces different failure modes and must not be described as exactly-once tool execution without an idempotent side-effect protocol.

### Crash semantics

The design must specify the point at which the confirmation is considered consumed. If consumption is durably committed before the tool call, a process crash after commit and before the side effect creates an authorization-loss/retry problem. If consumption is committed after the tool call, a crash after the side effect and before commit permits replay. The safer default is to consume before dispatch and require a separate idempotency/recovery protocol for retriable tools.

**DESIGN DECISION:** choose whether the system offers at-most-once authorization, at-least-once delivery with idempotent tools, or a transactional outbox/saga model. The existing evidence does not resolve this choice.

### Audit behavior

Every rejected concurrent attempt must produce an audit event with confirmation identity, scope digest, result `already_used` or the relevant refusal reason, and a timestamp from the authoritative store. Audit failure must not silently turn a rejected attempt into an accepted one.

### Concurrency test matrix

| Scenario | Expected result |
|---|---|
| Two threads, one event | Exactly one consume success |
| Many threads, one event | Exactly one consume success; no duplicate tool calls |
| Two processes, one event | Exactly one consume success when shared store is configured |
| Expired event under race | Zero consume successes |
| Scope mismatch under race | Zero consume successes for the wrong scope |
| Crash before conditional commit | No consumed state unless the store committed it |
| Crash after commit before tool | Event remains consumed; recovery path is explicit |
| Repeated caller after success | `already_used`; no handler invocation |

## 4. Immutable Confirmation Design

### Immutable fields

The issued confirmation identity must be immutable after creation:

- `confirmation_id`
- `request_id`
- `action`
- `tool_identity`
- `session_id`
- `payload_hash`
- `target_id`
- `target_version`
- `target_hash`
- `issued_at`
- `expires_at`
- `nonce`
- schema/version identifier

Verification must use the immutable stored representation rather than a caller-controlled mutable object.

### Defensive-copy requirements

Freezing a dataclass protects attribute assignment but does not protect mutable nested values. The confirmation contract should contain only scalar canonical values, immutable tuples, and immutable byte/string digests. It should not retain the raw payload or mutable target dictionaries. If a payload or target snapshot is exposed to callers, it must be a defensive immutable representation or a copy that cannot alter the event identity.

### Canonical identity

The confirmation identity should be a canonical tuple or serialized record containing:

```text
schema_version
confirmation_id
request_id
action
tool_identity
session_id
payload_hash
target_id
target_version
target_hash
issued_at
expires_at
nonce
```

The payload itself is represented only by its canonical hash in the confirmation identity. Canonical serialization must define object key ordering, list ordering, numeric handling, text encoding, and unsupported values. Unsupported values must be rejected rather than silently stringified.

`request_id` identifies the originating Core request. `confirmation_id` identifies the authorization event. They are distinct because one request may produce at most one or more explicitly modeled confirmation attempts, while each authorization event must remain individually auditable. **DESIGN DECISION:** decide whether AION permits more than one confirmation event per request. If not, enforce a one-to-one relation in the authoritative store.

### Confirmation ID decision

A dedicated `confirmation_id` is recommended. It prevents overloading `request_id` with both request identity and authorization-event identity. The current UUID-like `request_id` generated by `ConfirmationChannel` should not silently substitute for the Core request identity.

Dataclass freezing alone is insufficient because it does not prevent event substitution, stale object references, or mutation of nested data. The channel should resolve the event by immutable `confirmation_id` from its authoritative store and verify the stored record.

## 5. Tool Identity Design

### Identity model

The current architecture treats `action` as policy scope and `tool` as the registry lookup key. This is insufficient when one tool name can perform materially different actions with different payload contracts. The hardened design should use an explicit handler identity:

```text
handler_id = (action, tool, handler_version)
```

The action remains part of confirmation scope. The tool identifies the capability family. The handler version identifies the implementation contract when tools can be upgraded independently.

This model follows the existing architecture's distinction: `ConfirmationChannel` already checks action and tool, while the current registry checks tool only. The design closes the seam by making the lookup identity match the authorization identity.

**DESIGN DECISION:** determine whether `handler_version` is required at the first migration step. It is not established by current evidence, but it is necessary if the same action/tool can change implementation semantics without a new registration identity.

### Registry contract

The registry should register and resolve a structured key:

```text
(action, tool, handler_version) -> handler capability
```

Registration must reject duplicate keys. Unknown action/tool/version combinations must fail before invocation. A handler record should declare accepted payload schema, target mode, and tracing mode so that execution policy is not inferred from a string name alone.

### Confirmation contract

The confirmation must carry the exact handler identity that will be resolved. The boundary must compare event identity with the requested execution identity before consuming the confirmation. The event must not authorize a different handler merely because the tool name matches.

### Mismatch behavior and audit

Any action, tool, or handler-version mismatch must refuse before dispatch and must not consume the confirmation unless the chosen policy deliberately consumes invalid attempts to prevent probing. The default design preserves the current behavior of leaving a confirmation unused on scope mismatch. The audit should record requested identity, event identity, result, and whether the event remained consumable.

## 6. Payload / Tracing Design

### Supported payload types

The hardening design should choose one explicit contract rather than relying on incidental Python behavior. Three alternatives are possible:

| Choice | Security consequence | Compatibility consequence | Testing burden | Drift semantics |
|---|---|---|---|---|
| **A. Canonical payload type** | Strongest and easiest to reason about. Unsupported shapes cannot bypass tracing. | May reject existing list, custom mapping, and object callers. | Lowest after migration. | Every supported field access has one defined observation model. |
| **B. Expanded tracing** | Broad compatibility, but every access path must be defined and tested. | Preserves more callers. | Highest, including nested and alias behavior. | Depends on explicit recursive and reference semantics. |
| **C. Explicit unsupported classes** | Safe only if rejection happens before confirmation/execution, not by silent pass-through. | Requires callers to adapt. | Moderate; unsupported cases need rejection tests. | Unsupported classes never reach a tool. |

**DESIGN DECISION:** choose A, B, or C after inventorying real tools. Based on the current evidence, Choice A or C is preferable for a hardened first release. Choice B should not be adopted without a defined recursive model.

### Proposed default contract

The proposed default is a canonical, JSON-compatible mapping with string keys, immutable or copied nested values, and explicit list semantics. A `dict` may be accepted at the public boundary and immediately converted to a canonical immutable representation. A custom `Mapping` should either be normalized before issuance and execution or be rejected. It should not silently bypass tracing.

`TracingRow` should be an internal execution view over the canonical mapping, not an alternate authority source. If `TracingRow` is retained, the tool receives the view that corresponds exactly to the payload hash and target binding already verified.

### Tracing semantics

The design must state whether the following are reads:

- `row[key]`, `get`, and membership checks: yes, for the named key.
- `keys()` and iteration: enumeration only, unless a subsequent value read occurs.
- `items()`: each value read must be observable if the tracing model promises field-level coverage.
- nested mappings: recursive paths such as `user.id` must be represented explicitly.
- attribute access: unsupported unless the payload contract includes typed objects and an attribute tracer.
- aliases/references: canonicalization must define whether the same underlying value has one path or multiple paths.
- mutation: execution payloads should be read-only or copied; mutation after hashing must not alter the approved value.

### Unsupported types

Arbitrary objects, tuples with ambiguous serialization, custom mappings, and attribute-based payloads should be rejected or normalized before confirmation issuance. Silent pass-through is not acceptable for a payload class on which drift detection is a security requirement.

## 7. Audit Integrity Design

### Operational versus security evidence

The design separates four layers:

1. **Operational audit:** local diagnostics for issued, verified, consumed, rejected, and executed events.
2. **Security evidence:** structured records sufficient to reconstruct authorization and boundary decisions.
3. **Tamper-evident evidence:** records linked by a hash chain or authenticated digest so later modification is detectable.
4. **External durable audit:** storage outside the execution process with defined retention, access control, and recovery semantics.

The current `ConfirmationChannel._audit` is suitable only for operational, process-local evidence. It should not remain the authoritative security evidence source once multiple workers or durable audit requirements exist.

### Immutability and append-only behavior

`audit_log()` should return immutable record values, such as frozen records containing immutable nested fields, or serialized copies. Internal records should not be exposed by reference. Append-only means that application code cannot edit or delete a committed record; it does not by itself prove tamper resistance against a privileged storage operator.

### Canonical serialization and integrity

Every security evidence record should have a canonical serialization with stable field ordering, explicit schema version, and UTC timestamps. A hash chain can detect deletion or reordering when the chain head is protected. An HMAC can detect modification by parties without the key. A digital signature can support independent verification but requires key ownership and rotation.

**DESIGN DECISION:** choose the threat model and integrity mechanism. If the verifier and writer share the same process and key, an HMAC does not establish independent evidence. If third-party verification is required, a signature or externally protected chain head is needed.

### Persistence and failure policy

Durable audit should be written through an explicit adapter. The adapter must define whether an execution is allowed when audit persistence is unavailable:

- `AUDIT_REQUIRED`: refuse before side effect when the required pre-execution evidence cannot be committed; after a side effect, surface an indeterminate result and do not retry automatically.
- `AUDIT_BEST_EFFORT`: permit execution but record an explicit audit-loss event when possible; this mode must not be described as security evidence.

**DESIGN DECISION:** select the default per action risk class. The current implementation does not establish whether audit is authoritative for any action.

### Authoritative audit source

The future authoritative security evidence source should be the durable audit adapter or transactional store, not `ConfirmationChannel._audit`. The channel may retain a local operational buffer for diagnostics. Every record should include confirmation identity, Core request identity, handler identity, target binding, payload digest, policy result, execution result, and correlation timestamps.

## 8. Pipeline Execution Lifecycle

The intended lifecycle is:

```text
Pipeline
  ↓  Pipeline creates a Core Request and obtains model proposals as untrusted data.
Decision
  ↓  Core records reasoning, critique, risk, constitution, and agency outcome.
Agency Gate
  ↓  AgencyGate determines whether an action proposal is eligible; it does not execute.
Confirmation
  ↓  Confirmation service creates an immutable event only for an eligible action.
Target Capture
  ↓  Target resolver captures the target identifier, version, and canonical hash.
Human Confirmation
  ↓  An external confirmation actor approves the exact confirmation identity and scope.
ExecutionBoundary
  ↓  Boundary receives the immutable event and the requested handler identity.
Target Revalidation
  ↓  Boundary obtains the authoritative current target snapshot and compares it atomically.
Payload Verification
  ↓  Boundary computes the canonical payload hash and compares it with the event.
Tracing
  ↓  Boundary creates the supported tracing view over the same canonical payload.
Tool Resolution
  ↓  Registry resolves the exact action/tool/version handler identity.
Execution
  ↓  Tool receives the validated payload and target handle; side effects occur here only.
Audit
  ↓  Audit adapter records authorization, validation, dispatch, result, and failure state.
```

The Pipeline owns Core decision creation. AgencyGate owns agency classification. The confirmation service owns event issuance. The human or external confirmer owns approval of the displayed event. The target resolver owns target capture and current-state retrieval. ExecutionBoundary owns the final ordering and atomic authorization transition. ToolRegistry owns exact handler resolution. The tool owns the side effect. The audit adapter owns durable evidence.

The boundary must not call a tool before AgencyGate and confirmation. It must not validate a target and then allow the tool to resolve a different target. It must not treat a successful confirmation verification as proof that the tool executed successfully; execution outcome is a separate audit state.

## 9. Invariant Preservation Matrix

| Invariant | Current Evidence | Proposed Enforcement Point | Test Required |
|---|---|---|---|
| M-1: model proposes; Core decides | Selected Core parsing and AgencyGate tests | Typed Core-to-Agency interface; reject model authority fields | Injection and direct-construction tests |
| M-2: ACTION is not execution | Root agency tests; boundary tests | Separate `AgencyDecision` and execution state | State transition and no-tool-before-confirmation tests |
| M-3: no tool before gate/boundary | Local gateway-to-boundary tests only | Single executor entrypoint owned by boundary | Caller/path coverage and handler spy tests |
| M-4: confirmation is external authorization | Event required by current boundary path | Immutable confirmation plus external confirmer identity | Forged/mutated event and approval provenance tests |
| M-5: audit distinguishes attempt/result | Current evidence is partial and process-local | Durable audit schema with validation and result fields | Refusal, success, handler error, crash, and audit-loss tests |
| M-6: safety floors are lower bounds | Selected harmful-input tests | Deterministic safety floor before provider-derived risk | Pattern, obfuscation, and provider-collusion matrix |
| M-7: boundaries require evidence | Evidence map and Phase tests | Every enforcement claim paired with runtime test | Evidence-to-invariant review gate |
| M-8: confidence is not authority | Selected confidence barrier test | No direct authority field from model; deterministic barriers | High-confidence/low-evidence combinations |
| M-9: longitudinal context is not authority | Not established in current package | Keep context outside confirmation and identity stores | Cross-session authority and replay tests |
| I-6: LLM cannot grant execution authority | Not established as a complete current proof | Core recomputation plus boundary-owned confirmation | Adversarial provider and full-path tests |
| I-7: safety floor independent of model claims | Selected implementation evidence | Safety floor evaluated before model risk estimate | Model-low-risk harmful input tests |
| I-8: untrusted fields are sanitized | Sanitizer code and selected evidence | Schema validation before Core state construction | Invalid type, injection, bounds, and Unicode tests |
| I-9: refusal differs from clarification | Selected AgencyGate branches | Typed decision state and explicit transition policy | Accumulated constitution outcomes and formatting tests |

Additional hardening invariants are required for target binding, atomic single-use, immutable event identity, exact handler identity, supported payload types, and tamper-evident audit. Those are not replacements for the existing invariants; they enforce the seams revealed by Phase B and Phase C.

## 10. Migration / Compatibility Plan

No implementation is proposed in Phase D. The dependency order for a later migration is:

1. Define target, handler, payload, confirmation, audit, and execution-state contracts.
2. Add compatibility data types and adapters without changing existing behavior.
3. Introduce an explicit target mode for each action and inventory legacy undeclared actions.
4. Introduce immutable confirmation storage and preserve a read-only compatibility view for callers.
5. Introduce atomic consumption behind the existing channel interface.
6. Introduce exact handler identity and registration migration.
7. Select and enforce the payload contract, then expand or reject unsupported types.
8. Add target capture and revalidation to the boundary lifecycle.
9. Add durable audit with an explicit `AUDIT_REQUIRED` or `AUDIT_BEST_EFFORT` policy.
10. Connect Pipeline to the lifecycle only after the lower boundaries are independently verified.
11. Remove compatibility paths after all actions and callers have migrated.

Breaking API changes include adding required target state, changing event mutability, changing registry keys, rejecting unsupported payload classes, and requiring an audit adapter. Non-breaking alternatives include a new hardened boundary method, an adapter that maps legacy tool names to structured identities, and an explicit legacy mode that cannot claim hardened guarantees.

The rollback strategy should keep the current path available behind a feature boundary while the hardened path is exercised with shadow evidence. A rollback must not reuse a consumed confirmation or silently downgrade a target-bound action to unbound execution. If durable state has been committed, rollback must preserve its consumed and audit records.

## 11. Implementation Order

The order follows dependency and invariant requirements rather than preference:

1. Specify canonical identity and payload serialization.
2. Specify target and handler contracts.
3. Establish authoritative confirmation storage and atomic state transition.
4. Make confirmation identity immutable and link it to Core request identity.
5. Add exact handler registration and lookup.
6. Add the supported payload/tracing contract.
7. Add target capture and execution-time revalidation.
8. Add audit immutability, integrity, and persistence policy.
9. Integrate the Pipeline lifecycle.
10. Run concurrency, failure, TOCTOU, and invariant regression suites.
11. Deprecate and remove legacy compatibility behavior only after evidence exists for every migrated action.

## 12. Open Design Decisions

1. **Target resolver ownership:** boundary-owned resolution versus caller-supplied immutable snapshot.
2. **Target-free action inventory:** which actions may legitimately omit target binding.
3. **Legacy target mode:** whether undeclared legacy actions may execute during migration.
4. **Confirmation cardinality:** whether one Core request may create multiple confirmation events.
5. **Authoritative consume store:** process-local lock, transactional database, or another conditional-update store.
6. **Crash/retry model:** at-most-once authorization, at-least-once idempotent delivery, or transactional recovery protocol.
7. **Handler versioning:** whether `(action, tool)` is sufficient or a version is required immediately.
8. **Payload choice:** canonical restriction, expanded tracing, or explicit rejection of unsupported classes.
9. **Audit integrity:** hash chain, HMAC, signature, or externally protected append-only storage.
10. **Audit failure policy:** default use of `AUDIT_REQUIRED` or `AUDIT_BEST_EFFORT` by risk class.
11. **Human confirmation provenance:** how confirmer identity and approval time are represented and verified.

## 13. Explicit Non-Goals

Phase D does not implement any production change. It does not establish that the current system is secure, production-ready, tamper-proof, distributed-safe, or complete. It does not prove that a Python lock would solve multi-process or distributed execution. It does not select a final cryptographic mechanism, target resolver, persistence engine, payload contract, retry policy, or handler version policy.

It also does not add fail-closed behavior, target enforcement, immutable events, signatures, locks, tracing expansion, ToolRegistry changes, Pipeline integration, or audit persistence. Those are future implementation work subject to the open decisions above.

## References

[1]: ../AION_Constitution.md "AION Constitution"
[2]: ../AION_Invariants.md "AION Invariants"
[3]: ../KNOWN_LIMITATIONS.md "AION Proof-Phase Boundaries"
[4]: ../EVIDENCE_MAP_REVIEW_2026-09-16.md "AION Evidence Map Review"
[5]: ../aion/execution/channel.py "ConfirmationChannel implementation"
[6]: ../aion/execution/boundary.py "ExecutionBoundary implementation"
[7]: ../aion/binding/tracer.py "Runtime field tracing implementation"
[8]: ../aion_core\ \(1\).py "AION Core snapshot"
[9]: ../tests/test_phase_b_boundary_evidence.py "Phase B boundary evidence tests"
[10]: ../tests/test_phase_c_hardening_evidence.py "Phase C hardening evidence tests"

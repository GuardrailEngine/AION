# Phase E.2R — Target Authority Design

**Status:** Design only. This document does not implement target binding, create a resolver, or modify production code or tests.

## 1. Evidence Baseline

The current architecture contains two separate concepts that are both called target-related but are not connected by an authoritative state source.

`ConfirmationChannel` can compare a confirmation's `target_version` and `target_hash` with caller-supplied `current_target_version` and `current_target_hash`. Phase B and Phase C tests established that this validation exists at the channel level. Phase E.1 preserved confirmation immutability and thread-scoped atomic consumption.

`ExecutionBoundary.execute()` currently receives an event, action, tool, session, and payload. It does not receive a current target snapshot or a target resolver. It verifies the payload and confirmation scope, consumes the event, and dispatches the tool. Phase E.2 therefore established that target binding at the actual execution boundary is **NOT ESTABLISHED**.

`AgencyGateway` accepts a request dictionary and copies optional `target_version` and `target_hash` values into the issued confirmation. It does not resolve a resource, read current state, compute a target version, or compute a target hash. The caller remains the source of those values.

The binding package can hash a mapping according to an `ActionBinding`. For a partial binding it selects declared fields; for a full-row binding it hashes the whole row. That function is a target-row hashing utility, not a target authority and not a current-state resolver. It is not automatically connected to `AgencyGateway` or `ExecutionBoundary`.

The current evidence classifies the lifecycle as follows:

| Value or operation | Current source | Classification |
|---|---|---|
| `request.target_version` | Caller request | **CALLER-PROVIDED, UNVERIFIED** |
| `request.target_hash` | Caller request | **CALLER-PROVIDED, UNVERIFIED** |
| `AgencyGateway` target fields | Copied from request | **COPIED, UNVERIFIED** |
| `ConfirmationEvent.target_version` | Gateway input at issuance | **COPIED, IMMUTABLE AFTER E.1, NOT AUTHORITATIVE** |
| `ConfirmationEvent.target_hash` | Gateway input at issuance | **COPIED, IMMUTABLE AFTER E.1, NOT AUTHORITATIVE** |
| `ConfirmationChannel.verify()` current values | Verification caller | **CALLER-SUPPLIED AT VERIFICATION** |
| `hash_row_by_binding()` result | Derived from a supplied mapping and binding | **DERIVED, NOT CURRENT-STATE AUTHORITY** |
| `ExecutionBoundary` current target | No source exists | **UNKNOWN / STRUCTURAL GAP** |
| Tool target state | Tool-specific and unspecified | **UNKNOWN** |

No existing component in the current package owns current target state. The design must not treat confirmation values as current values merely because they are immutable.

## 2. Current Target Lifecycle

The current path is:

```text
caller request
    ↓
request.get("target_version") / request.get("target_hash")
    ↓
AgencyGateway.route()
    ↓  copies both optional values
ConfirmationChannel.issue()
    ↓
immutable ConfirmationEvent
    ↓  event is handed to caller
ExecutionBoundary.execute()
    ↓  no current target read or resolver call
ConfirmationChannel.verify_and_consume()
    ↓  current target arguments are omitted by Boundary
ToolRegistry.get(tool)
    ↓
Tool(payload)
```

The current target values originate in caller input. The gateway does not establish semantic trust. The confirmation event preserves the values after Phase E.1, but immutability preserves identity; it does not make caller-provided values authoritative. The execution boundary has no opportunity to compare the event with the actual resource state immediately before dispatch.

The existing `ActionBinding` definitions describe which fields matter for drift detection and row hashing. They do not identify a resource store, a resource identity, a revision source, or a mutation authority. The current binding layer therefore supplies hashing semantics but not target ownership.

## 3. Structural Gap

The immediate gap is not the comparison operation. The comparison operation already exists in `ConfirmationChannel`. The gap is the absence of a component that can answer, authoritatively and at execution time:

1. Which resource is the target?
2. What is its current version or generation?
3. What canonical fields currently define its target hash?
4. Which snapshot will the tool actually use?
5. Can the target change between the final read and the tool's side effect?

Adding optional `current_target_version` and `current_target_hash` parameters to `ExecutionBoundary` without an authority source would only move caller-provided data to another method. It would not establish the invariant. Adding a synthetic in-memory resolver would create a test fixture, not an authority model.

This is a **STRUCTURAL GAP**. It blocks target-binding enforcement and complete TOCTOU claims until a real target owner is identified and integrated.

## 4. Target Authority Model

### What is a target?

In the current AION code, a target is not a defined domain object. The binding layer operates on a mapping or row and selects fields by action. Therefore the only evidence-supported description is:

> A target is the external resource or state row whose action-relevant representation is intended to be affected or read by a tool.

The exact resource class is not established. It could be a file, profile row, record, or another tool-owned object. Existing names such as `delete_file` and `update_profile` show examples, but they do not define one common resource store.

### Proposed authority owner

The future authority should be a **resource-specific `TargetAuthority` adapter** owned by the subsystem that owns the resource state. AION should not become the owner of file-system, profile, database, or external-service state. The adapter should expose read and, where supported, preconditioned mutation operations.

Conceptually:

```python
class TargetAuthority(Protocol):
    def snapshot(
        self,
        *,
        action: str,
        target_ref: TargetRef,
    ) -> TargetSnapshot:
        ...
```

This is a design interface, not an implementation proposal for the current package. A real adapter must be connected to an existing resource owner. Until such an owner is identified, target authority remains **NOT ESTABLISHED**.

### Ownership and mutation

The resource subsystem owns current state and decides which reads are authoritative. The target authority may read the state through that subsystem. Only the resource owner or its approved mutation API may mutate the resource. AION's confirmation channel must not become a second source of truth, and a caller must not be able to manufacture authority by supplying version or hash strings.

### Version and hash production

The target authority, or a canonicalization routine controlled by the resource owner, must produce `target_version` and `target_hash` from the same snapshot. The gateway must receive that snapshot rather than accepting independent caller strings. The execution boundary must request a fresh snapshot from the same authority immediately before dispatch.

### Snapshot capture

The first snapshot is captured before confirmation issuance and displayed as part of the exact human-confirmation scope. The second snapshot is obtained by the execution boundary after confirmation approval and before tool resolution or dispatch. The second snapshot is authoritative for the current-state comparison because it comes from the resource owner, not from the confirmation caller.

## 5. Target Snapshot Contract

The minimum conceptual contract is:

```python
@dataclass(frozen=True)
class TargetSnapshot:
    target_ref: TargetRef
    version: str
    content_hash: str
    source: str
```

The fields have these roles:

- `target_ref` identifies the concrete resource. A version and hash without identity could compare the right representation from the wrong object.
- `version` is the resource owner's concurrency or generation token. It is required only if the resource owner provides a meaningful token; for a target-bound action, the hardened contract should require it rather than accept an arbitrary caller string.
- `content_hash` is the digest of the canonical action-relevant target representation.
- `source` records which authority adapter produced the snapshot. It is useful for audit and diagnostics, but it is not itself an authorization decision.

A timestamp is not a substitute for a version. It may be recorded for audit, but wall-clock time does not prove that the target is unchanged. A lifecycle marker or generation token may be included when the resource owner exposes one; it should not be invented by AION.

The current architecture does not have `TargetRef`, a target identity field, an authoritative `version`, or a source/provenance field. These are **DESIGN DECISIONS / STRUCTURAL GAPS**, not existing runtime contracts.

The confirmation should store the immutable target identity and the two comparison values. The tool should receive the validated snapshot or an authority-issued target handle, not a fresh unconstrained lookup. The exact handle design depends on the resource subsystem.

## 6. Target Version Semantics

In the current package, `target_version` is an arbitrary optional string supplied by the caller or request. No monotonicity, database revision, object generation, or immutable identity semantics are enforced. Its current classification is:

```text
CALLER-PROVIDED / UNVERIFIED / SEMANTICALLY UNKNOWN
```

A future `target_version` must mean the resource owner's concurrency token or object generation. It must not mean the confirmation ID, request ID, issuance timestamp, or a caller-selected label. The authority must define whether values are monotonic, unique per resource, and never reused for a different resource generation.

If the resource owner has no revision or generation concept, the system cannot claim version-based concurrency protection. It must either use a resource-owner-supported atomic snapshot/read or classify the action's target binding as unable to provide the required guarantee. AION must not synthesize a version from local time or a process counter and present it as resource authority.

The current evidence does not identify a valid version source. Therefore the semantics are **DESIGN DECISION / STRUCTURAL GAP**.

## 7. Target Hash Semantics

### Existing implementation

`hash_row_by_binding(row, binding)` accepts a mapping and derives a digest through `hash_payload()`:

- For a full-row binding `("*",)`, it converts the row to a dictionary and hashes the full selected row.
- For a field binding, it requires each declared field and hashes a dictionary containing only those fields.
- `hash_payload()` uses JSON serialization with sorted keys and compact separators, then SHA-256 over UTF-8 bytes.
- Missing bound fields raise an error.
- Unknown actions fall back to a full-row binding in `get_binding()`.

This is the current hashing baseline. It does not establish that the supplied row is the current resource state.

### Required separation

`payload_hash` binds the payload presented to the confirmation and execution boundary. `target_hash` binds the action-relevant representation of the target resource. They are distinct values and must be computed from distinct inputs:

```text
payload_hash = H(canonical execution payload)
target_hash  = H(canonical action-relevant target snapshot)
```

The target authority must compute the target hash from the authoritative snapshot. A caller must not be able to replace it with a hash of arbitrary payload data. Existing code currently allows caller-supplied `target_hash`; that is part of the structural gap.

### Relationship to version

The version identifies a resource generation according to the resource owner's semantics. The hash identifies the action-relevant content of that generation. Both are useful because a version can be ambiguous or reused and a hash without resource identity can be detached from the object it describes. A target-bound action should compare both when both are available and required by its authority contract.

For a target row that changes in an unrelated field, a partial action binding may deliberately keep the same target hash. That is a policy choice represented by `ActionBinding`; it is not evidence that the entire row is unchanged. Full-row and relevant-field bindings must remain distinct.

## 8. Authority Flow

The future flow should be:

```text
TargetAuthority
    ↓ TargetRef + authoritative snapshot
TargetSnapshot
    ↓ target identity + version + hash
Confirmation issuance
    ↓ immutable confirmation scope
Human confirmation
    ↓ approval of exact event identity
ExecutionBoundary
    ↓ request a fresh snapshot from the same authority
CURRENT TargetSnapshot
    ↓ compare target identity/version/hash
Tool
```

| Arrow | Responsible component | Data | Trust level | Mutation authority | Validation responsibility |
|---|---|---|---|---|---|
| Authority → snapshot | Resource-specific TargetAuthority | TargetRef, canonical state, version, hash | Authoritative for that resource | Resource owner | Validate resource existence and canonical read |
| Snapshot → issuance | Agency/confirmation coordinator | Immutable snapshot binding | Derived from authority | No mutation | Ensure action and target contract agree |
| Issuance → human | Confirmation service | Immutable event identity and scope | Untrusted until external approval | No mutation | Display exact action, tool, payload, and target binding |
| Human → boundary | External confirmer/caller | Event identity and approval evidence | External authorization input | No target mutation | Verify event identity and approval provenance |
| Boundary → current snapshot | ExecutionBoundary through TargetAuthority | Fresh resource snapshot | Authoritative current read | No mutation during read | Obtain fresh state immediately before dispatch |
| Comparison → tool | ExecutionBoundary | Validated snapshot/handle | Validated for the tested boundary | Tool may mutate only through preconditioned API | Compare identity, version, and hash before resolution/dispatch |
| Tool → resource | Tool/resource API | Validated handle and payload | Action-authorized execution | Resource owner controls mutation | Enforce version/hash precondition where supported |

Caller-provided target strings may be included as a request hint, but they must not be accepted as the authority result. Confirmation identity remains immutable, but the confirmation is not the owner of target state.

## 9. TOCTOU Model

The current architecture supports none of the target consistency models end to end because it has no target authority. The design comparison is:

| Model | What it can prevent | What remains | Current support |
|---|---|---|---|
| Immutable target | State changes to an actually immutable object | Wrong object selection if identity is weak | **NOT ESTABLISHED** |
| Versioned target | Changes that advance the authoritative generation before the final check | ABA if versions can be reused; race after check | **NOT ESTABLISHED** |
| Version + hash | Version changes and action-relevant content changes; hash helps with ABA | Race after the final read unless the side effect uses a precondition | **DESIGN TARGET** |
| Atomic snapshot/read | Inconsistent reads during snapshot acquisition | Mutation after snapshot unless coupled to execution | **NOT ESTABLISHED** |
| Transactional compare-and-execute | Change between comparison and side effect when the resource owner supports the transaction | External side effects outside the transaction | **NOT ESTABLISHED** |

The minimum future guarantee should be a fresh authority snapshot immediately before tool dispatch, followed by comparison of target identity, version, and hash. This prevents execution from using a stale confirmation when the authority reports a changed target before dispatch.

It does not eliminate a race in which the resource changes after the final read and before the tool's side effect. Complete TOCTOU prevention requires the tool/resource API to accept the validated version or hash as a compare-and-execute precondition, or to execute inside an authority-controlled transaction. The current AION architecture does not provide either capability.

The target authority must also define whether tool execution itself mutates the target. A read-only tool may require only a stable snapshot; a mutating tool must use a resource-owner precondition if the invariant includes state continuity through the side effect.

## 10. Target-Free Actions

The current code does not contain an explicit target mode. `get_binding()` returns a full-row default for unknown actions, which is not evidence that an action is target-free. Existing action names are insufficient to classify target requirements without tool contracts and resource ownership information.

A future action should be classified as target-bound when its outcome depends on a concrete external resource, row, file, account, record, or state transition whose identity or contents can change between confirmation and execution. It may be target-free only when the action contract explicitly declares that it has no external mutable target and the tool cannot resolve or mutate one indirectly.

The classification must be declared by the action capability contract and reviewed against the actual tool implementation. Omission must not mean target-free. A target-bound action with missing authority must be rejected or remain unavailable for hardened execution.

Current classification:

```text
Existing actions: NOT ESTABLISHED
Target-free action inventory: NOT ESTABLISHED
Unknown-action full-row fallback: SUPPORTED HASHING FALLBACK, NOT TARGET-FREE AUTHORITY
```

## 11. Failure Model

The future authority and boundary should preserve distinct failure classes:

| Condition | Classification | Proposed result |
|---|---|---|
| Target not found | Validation/resource failure | No confirmation issuance for a new target; no execution for a missing current target |
| Target version unavailable | Infrastructure or authority-contract failure | Refuse target-bound execution; do not substitute confirmation value |
| Target hash unavailable | Infrastructure or canonicalization failure | Refuse target-bound execution; do not execute on version alone unless the action contract explicitly permits it |
| Resolver unavailable | Infrastructure failure | Refuse before tool dispatch and audit resolver unavailability |
| Target changed | Target drift | Refuse before tool dispatch; preserve the confirmation for explicit policy-defined handling or consume according to the atomic confirmation policy |
| Target deleted | Target drift/resource failure | Refuse; do not reinterpret deletion as unchanged |
| Target recreated | Identity/generation failure | Refuse unless the authority proves the same target identity and approved generation |
| Target version reused | Version-integrity failure | Hash and target identity must detect it; otherwise the authority contract is insufficient |
| Hash mismatch | Target drift | Refuse before tool dispatch |
| Version mismatch | Target drift | Refuse before tool dispatch |

A validation failure means the requested execution scope is malformed or incomplete. Target drift means the resource state differs from the approved state. Infrastructure failure means the authority could not provide a trustworthy answer. Authorization failure means the confirmation or policy scope is invalid. None of these may be silently converted into “target unchanged.”

The current package does not implement these boundary results. They are **NOT IMPLEMENTED** design semantics.

## 12. ExecutionBoundary API Design

### Candidate A: boundary receives `TargetSnapshot`

This is easy to test but unsafe if the caller can construct or replace the snapshot. It can be acceptable only when the snapshot is an authority-issued immutable object whose provenance is validated by the boundary. The current package has no such object.

### Candidate B: boundary receives `TargetResolver`

This makes the boundary ask for current state, which is better than accepting caller strings. It still requires the resolver to be a genuine resource-owner adapter and requires clear rules for target references, failure, and snapshot lifetime. Dependency injection makes the path testable without making a synthetic resolver authoritative in production.

### Candidate C: boundary receives `TargetHandle`

An authority-issued handle can bind identity and a compare-and-execute precondition to the tool. This offers the strongest TOCTOU story when the resource owner supports it, but the current architecture has no handle protocol and no resource transaction interface.

### Decision

The preferred future boundary dependency is a resource-specific `TargetAuthority` or resolver injected into `ExecutionBoundary`, with the resolver returning an immutable `TargetSnapshot` and, where required, an authority-issued `TargetHandle` for the tool. The caller should supply a target reference or action request, not authoritative current version/hash values.

Conceptually:

```python
ExecutionBoundary(
    channel,
    registry,
    target_authority: TargetAuthority,
)

ExecutionBoundary.execute(
    event,
    action,
    tool,
    session_id,
    payload,
    *,
    target_ref,
    request_id,
)
```

The boundary would resolve the current snapshot immediately before consuming/dispatching according to the chosen atomic ordering, compare it to the immutable confirmation binding, and pass the validated snapshot or handle to the tool. The exact ordering between target resolution and confirmation consumption must be aligned with the Phase E.1 consume/crash policy.

This is a **DESIGN DECISION**, not an implemented API. The current architecture cannot support it until a real target owner and target reference contract are introduced.

## 13. Invariant Preservation

The proposed target authority does not grant authority to the LLM, Core, or confirmation object. It places current-state authority with the resource owner and keeps policy authorization in the existing path:

```text
LLM
→ Core
→ AgencyGate
→ ExecutionPolicy
→ Human Confirmation
→ ExecutionBoundary
→ Tool
```

The following invariants are preserved:

- **I-6:** target state is resolved only at the boundary from a resource authority; it is not created by model output.
- **M-8:** risk, confidence, critique, or any other LLM-derived metric cannot create target authority.
- **M-9:** longitudinal context remains non-authoritative.
- **M-1:** non-execution remains distinct from correctness; a refusal does not prove that the target was correct.
- Caller-provided target data remains a hint or requested scope until the resource authority confirms it.
- Immutable confirmation identity remains separate from current target authority.
- Target drift cannot silently become executable.
- Payload hash and target hash remain separate bindings.

The design does not change existing HIGH binding-drift tracing policy. Runtime tracing and target authority answer different questions: tracing observes field access, while the target authority establishes which external state is current.

## 14. Migration Dependencies

A future implementation depends on the following prerequisites, in order:

1. Identify at least one real resource owner and document its target reference.
2. Define the resource owner's version/generation semantics.
3. Define canonical action-relevant target representation and hashing inputs.
4. Define target-free versus target-bound action metadata from actual tool contracts.
5. Implement an authority adapter that reads current state from the real resource owner.
6. Add immutable `TargetSnapshot` and, if needed, an authority-issued `TargetHandle`.
7. Change confirmation issuance to obtain the snapshot from the authority rather than copying caller strings.
8. Inject the same authority into the execution boundary and add final revalidation.
9. Add tests for matching state, drift, missing state, authority failure, deletion, recreation, and post-check mutation.
10. Add a resource-owner compare-and-execute contract before claiming complete TOCTOU protection.

No migration step should enable hardened target-bound execution while the authority source is missing. A compatibility mode may preserve the existing caller-provided path for evidence or non-hardened legacy operation, but it must be labeled **NOT ESTABLISHED** and must not be described as target enforcement.

## 15. Open Design Decisions

1. Which concrete resource subsystem will provide the first `TargetAuthority` implementation?
2. What is the authoritative target reference for each existing tool?
3. Does each resource owner expose a monotonic revision, an object generation, or another concurrency token?
4. Can the first resource owner provide compare-and-execute semantics, or only a final read?
5. Which action contracts are target-bound, and which are explicitly target-free?
6. Should the execution boundary receive a resolver, a snapshot, or an authority-issued handle after the first real resource integration is selected?
7. Should a target drift leave the confirmation unused for explicit reapproval, or consume it as a rejected authorization attempt?
8. What provenance data can be independently verified for a snapshot?
9. How should deletion and recreation be represented when an external identifier is reused?
10. What canonicalization rules are required for resource-specific mappings, numeric values, and unsupported types?
11. Which target authority failures are `AUDIT_REQUIRED` before any side effect?

These decisions cannot be resolved from the current AION package because it contains no target resource owner or current-state resolver.

## 16. Explicit Non-Goals

This document does not implement target binding, a target resolver, a target snapshot class, a target handle, a new `ExecutionBoundary` signature, or any target comparison at execution time.

It does not modify `ConfirmationChannel`, `ExecutionBoundary`, `AgencyGateway`, `ToolRegistry`, `Pipeline`, binding/tracing code, requirements, CI, Makefile, or tests. It does not create a synthetic in-memory resolver. It does not claim complete TOCTOU prevention, process/distributed guarantees, cryptographic authenticity, durable audit integrity, or target-free classification.

The only permitted artifact for Phase E.2R is this design document.

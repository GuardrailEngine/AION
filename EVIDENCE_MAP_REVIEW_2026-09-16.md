# AION Evidence Map Review — Available Package

**Scope:** `/home/ubuntu/aion_project`

**Review basis:** Files physically present in the extracted package, direct source inspection, fresh pytest execution, and temporary non-persistent probes. The existing core and agency test were not modified. The ConfirmationChannel, ExecutionBoundary, AgencyGateway, and real-gate adapter packages and their focused tests were added as new files from supplied task specifications.

## Evidence classification

| Classification | Meaning in this review |
|---|---|
| **Observed / Reproduced** | Behavior was executed or directly reproduced from a file present in the package. |
| **Historical** | Preserved output or version claim from the package; not re-executed in this workspace. |
| **Documented only** | Described by package documentation without corresponding available runtime artifacts here. |
| **Not available** | The referenced source or test artifact is absent from the extracted package. |
| **Not tested** | A component is present or inspectable, but the relevant property was not established by a current test/probe. |

## Current evidence map

| Component / boundary | Current classification | What the package establishes | Important limits |
|---|---|---|---|
| Python syntax | **Observed / Reproduced** | Available Python files compile successfully. | Syntax validity is not behavioral correctness. |
| CLI in `aion_core (1).py` | **Observed / Reproduced** | `--stub` execution produced a decision and status output. | Interactive and external-provider paths were not fully tested. |
| `AgencyGate` selected branches | **Observed / Reproduced** | Selected I-1 to I-5, irreversible-risk, low-intent, and M-8 paths were directly inspected/probed; the package test source covers selected gate behavior. | Does not establish upstream input validity, all gate branches, or external execution behavior. |
| `ConstitutionChecker` selected branches | **Observed / Reproduced** | All six implemented checks were exercised through a temporary direct probe, including PASS, NOTICE, CLARIFY, FAIL_ENFORCEABLE, and accumulated outcomes. | No permanent runnable checker regression test exists in the package. |
| `Safety Floor` | **Observed / Reproduced** | Arabic and English harmful patterns returned `CRITICAL`; a benign query returned no floor. | Completeness of `HARM_PATTERNS` is **Not tested** and explicitly unknown in documentation. |
| `Execution Policy` / `verify_execution_need` | **Observed / Reproduced** | Action wording with `TASK` returned true; explanatory wording, non-task intent, and missing action wording returned false. | Pattern completeness and semantic coverage are **Not tested**. |
| Trust sanitizers | **Observed / Reproduced** | `safe_enum`, `safe_confidence`, `safe_bool`, `safe_str`, and `safe_str_list` were exercised on invalid, bounded, and injection-like values. | These are current snapshot observations, not a complete sanitization proof. |
| `_safe_parse` and reasoning parser | **Observed / Reproduced** | Valid JSON extraction, invalid JSON fallback, structured reasoning, and empty answer parsing were reproduced. | Parser robustness beyond exercised strings is **Not tested**. |
| Risk helpers | **Observed / Reproduced** | Factor extraction/clamping and risk classification thresholds were reproduced for selected values. | Full threshold matrix and provider-originated risk correctness are **Not tested**. |
| `StubProvider` | **Observed / Reproduced** | Deterministic fallback behavior and prompt recording are present and usable. | No claim about external model behavior. |
| `AdversarialProvider` | **Observed / Reproduced** | Selected modes were run through `Pipeline`; outputs reached deterministic gate states. | This does not prove complete adversarial coverage or the historical C-family. |
| `DeepSeekProvider` | **Not tested** | Source includes an external-provider implementation requiring an API key and dependency. | No external call was made; provider behavior is not runtime evidence here. |
| `AuditLog` | **Observed / Reproduced** | Temporary-path write, read, lookup, and missing-record behavior worked. | Filesystem tampering, durability, concurrency, and tamper resistance remain **Not tested / Out of Scope**. |
| `MockTool` | **Observed / Reproduced** | Direct invocation sets `called`, stores payload, and returns a result. | This does not establish an execution boundary or non-invocation guarantee. |
| `Pipeline` with Stub/Adversarial providers | **Observed / Reproduced** | End-to-end composition through intent, reasoning, critique, risk, constitution, agency, formatting, and audit was run for selected scenarios. | This is selected composition evidence, not a full regression environment. |
| `ConfirmationChannel` (`aion/execution/channel.py`) | **Observed / Runtime-verified** | Bound to `action`, `tool`, `session`, `request_id`, `payload_hash`, and `target_version`; rejection reasons include `already_used`, `expired`, `request_id_mismatch`, `action_mismatch`, `tool_mismatch`, `session_mismatch`, `payload_mismatch`, and `target_drift`. Verified by 18 focused tests. | Channel is verified in isolation and through the boundary pipeline below; real external tools remain out of scope. |
| `ExecutionBoundary` (`aion/execution/boundary.py`) | **Observed / Runtime-verified** | Re-verifies confirmation before dispatching to a tool; rejects `payload_mismatch`, `action_mismatch`, `unknown_tool`, and `already_used`; handles `tool_error:<ExceptionType>`. `ToolRegistry` `register`, `get`, and `has` are covered by the exercised path. Verified by 6 tests in `tests/test_execution_boundary.py`. | Boundary and Channel are verified in isolation and as a two-layer pipeline; real external tools and end-to-end regression remain out of scope for this package. |
| `AgencyGateway` (`aion/agency/gateway.py`) | **Observed / Runtime-verified** | Bridges AgencyGate-style decisions to `ConfirmationChannel`; issues confirmation for ACTION without consuming it; rejects `missing_field:<key>`; verified by 6 tests in `tests/test_agency_gateway.py`, including gate → confirmation → boundary → local tool flow. | Gateway uses an injected evaluator and does not prove the concrete `AgencyGate`/`Pipeline` integration. Real external tools and broader regression remain out of scope. |
| `real_gate_adapter` (`aion/agency/real_gate_adapter.py`) | **Observed / Runtime-verified** | The adapter imports and loads the available `aion_core (1).py` snapshot, refuses missing/`None` gate inputs, maps Core decisions to `(is_action, reason)`, and passes real Core objects through `AgencyGate.decide()`. Three adapter tests plus two end-to-end tests pass. | The concrete `AgencyGate` integration is verified for the deterministic ACTION fixture only; broader decision coverage remains **Not tested**. |
| `real_gate_e2e` (`tests/test_real_gate_e2e.py`) | **Observed / Runtime-verified** | Two tests cover real `AgencyGate.decide()` → adapter → `AgencyGateway` → `ConfirmationChannel` → `ExecutionBoundary` → local tool, using typed fixtures from `tests/fixtures_core.py`. | Uses a local test tool; real external tools and broader Core/Pipeline regression remain out of scope. |
| `execute_decision` | **Observed / Reproduced** | Current snapshot raises `NotImplementedError` with execution disabled. | This remains separate from the new isolated Channel → Boundary evidence. |
| `Executor` (standalone) | **Not available** | Documentation and manifest refer to an executor component. | Its source file and tests are absent from this extracted package. |
| External tools | **Not available / Out of scope** | No real external tool implementation is present. | The registry tests use local test functions only. |
| I-6 to I-9 broader evidence | **Historical / Documented only** | Historical outputs and documents describe broader tests. | Current package cannot reproduce the broader suite. |
| 45-test / 89-test results | **Historical** | Preserved text and documentation contain these claims. | They were not freshly executed from this package. |
| Full regression environment | **Not available** | The focused test suite and local CI-equivalent are runnable, but no broader complete suite/configuration is established. | Historical regression claims remain historical. |

## Directly reproduced additional components

### Safety Floor

The current implementation scans `HARM_PATTERNS` and returns `RiskLevel.CRITICAL` for selected Arabic and English direct-harm, self-harm, weapons, and fraud phrases. A benign question returned `None` in the probe.

This establishes selected pattern behavior only. It does not establish completeness, recall, resistance to obfuscation, or language coverage.

### Execution Policy

`verify_execution_need()` returned `True` for a `TASK` containing an action pattern such as `احذف الملف` or `نفّذ المهمة`. It returned `False` for explanatory language, non-`TASK` intent, and a task without an action pattern.

This is direct evidence for selected pattern combinations, not a general proof that external action need is classified correctly.

### Trust and parsing helpers

The probe reproduced enum fallback, confidence clamping/defaulting, strict boolean acceptance, string cleaning/truncation, list filtering, JSON extraction, and reasoning-section parsing. One current-snapshot observation is material:

```text
safe_confidence("infinity") -> 1.0
```

This is recorded as **Observed / Reproduced** behavior of the available snapshot. It is not classified here as a defect, because defect status requires an explicit expected semantic and a separate review. The package's historical changelog mentions an older confidence-sanitization defect, but that mention remains **Historical** for this workspace.

### Risk helpers

Selected factor inputs were clamped and classified. The implementation computes a score from severity, probability, non-reversibility, and a logarithmic affected-parties factor, then applies fixed thresholds for LOW, MEDIUM, HIGH, and CRITICAL.

The probe does not establish that model-supplied factors are truthful or that the complete risk pipeline always applies the safety floor before provider-derived estimates.

### ConfirmationChannel

The focused ConfirmationChannel tests produced fresh runtime evidence:

- `tests/test_confirmation_channel.py` — 15 passed
- `tests/test_target_drift.py` — 3 passed
- Total — **18/18 passed**, exit code `0`

The fresh tests cover scope binding across action, tool, session, request identity, payload hash, target version, expiry, and single-use state. They also cover canonical payload hashing, mutation before and after consumption, target drift, audit entries, and the `verify_and_consume()` path.

### ExecutionBoundary

The focused ExecutionBoundary integration tests produced fresh runtime evidence:

- `tests/test_execution_boundary.py` — 6 passed
- Full available `tests/` suite before AgencyGateway addition — **24/24 passed**, exit code `0`

The six tests cover valid dispatch, payload mutation rejection before tool invocation, unknown-tool rejection, action mismatch rejection, tool-error handling, and single-use confirmation at the boundary.

### AgencyGateway

The focused AgencyGateway tests produced fresh runtime evidence:

- `tests/test_agency_gateway.py` — 6 passed
- Full available `tests/` suite after addition — **30/30 passed**, exit code `0`

The tests cover INFO routing without confirmation, ACTION routing with confirmation issuance, missing-field rejection, target-version propagation, payload mutation rejection at the boundary, and the end-to-end local flow:

```text
gate → confirmation → boundary → ToolRegistry → local test tool
```

The gateway is issue-only: it does not consume the confirmation. Consumption remains the responsibility of `ExecutionBoundary` through `verify_and_consume()`.

### Real-gate adapter and end-to-end path

The adapter test file produced fresh runtime evidence:

- `tests/test_real_gate_adapter.py` — 3 passed
- `tests/test_real_gate_e2e.py` — 2 passed
- Full available `tests/` suite after addition — **35/35 passed**, exit code `0`

The adapter loads the available core snapshot, maps the real gate's expected call shape, refuses to fabricate missing inputs, and exposes a mapping helper. The new typed fixtures provide actual `Request`, `Reasoning`, `Critique`, `Risk`, and `ConstitutionResult` objects. The real `AgencyGate.decide()` returned `ACTION` with `action_requires_confirmation`, and the full local path completed through confirmation, boundary verification, and tool dispatch.

The verified path is:

```text
real AgencyGate.decide → real_gate_adapter → AgencyGateway → ConfirmationChannel → ExecutionBoundary → local test tool
```

### Local CI-equivalent

The `Makefile` pipeline was rerun after the typed-fixture addition:

- Pytest: **35 passed**
- Coverage on `aion/*`: **97%** (`187` statements, `6` missed)
- Bandit: **No issues identified**
- `make ci`: completed successfully

This is local CI-equivalent evidence only. It is not evidence that GitHub Actions has run remotely.

### AuditLog and Pipeline

`AuditLog` successfully wrote a serialized decision to a temporary JSONL path and returned it through `read_all()` and `find()`. A selected `Pipeline` run with `StubProvider` produced a decision and one audit record. Selected adversarial-provider modes also traversed the pipeline.

These observations establish selected local composition paths only. They do not establish tool non-invocation, confirmation handling through the concrete `aion_core` AgencyGate, external execution, concurrency behavior, or production audit integrity.

## Explicit Not tested boundary

- Real AgencyGate integration is verified for the typed deterministic ACTION fixture and the local end-to-end path.
- Broader AgencyGate branch coverage, concrete `aion_core` Pipeline orchestration, real external tools, and production execution remain **Not tested / Out of scope**.
- The existing `AgencyGateway` injected-evaluator tests remain separate evidence from the new real AgencyGate integration.

## Documentation and historical artifacts reviewed

The following files were reviewed as documentation or preserved evidence rather than fresh runtime proof:

- `KNOWN_LIMITATIONS.md`
- `EXTERNAL_SIGNALS.md`
- `AION_Origin_and_Provenance.md`
- `ORIGIN.md`
- `CHANGELOG.md`
- `FROZEN_VERSIONS.md`
- `AION_Security_Flow_Report.md`
- `AION_Repository_Manifest.md`
- `AION_Invariants.md`
- `AION_Constitution.md`

These documents consistently describe a broader proof phase, execution runtime, and 89/89 baseline. The ConfirmationChannel, ExecutionBoundary, AgencyGateway, adapter, typed fixtures, and focused end-to-end tests are now present and freshly executed; the referenced standalone Executor and broader regression artifacts remain absent from this package. Their claims therefore remain **Historical** or **Documented only / Not available** where not freshly reproduced here.

## Updated baseline statement

> The available package contains fresh, directly reproducible evidence for the Python snapshot, CLI, selected AgencyGate and ConstitutionChecker branches, selected safety/trust/policy/risk helpers, isolated ConfirmationChannel behavior (18/18 focused tests), isolated and two-layer ExecutionBoundary behavior (6/6 focused tests), AgencyGateway coordination and local end-to-end flow (6/6 focused tests), real AgencyGate → adapter → gateway → boundary → local tool behavior (2/2 typed-fixture tests), adapter loading and missing-input behavior (3/3 tests), local CI-equivalent execution (35 tests, 97% aion coverage, no Bandit issues), local AuditLog behavior, MockTool behavior, and selected Pipeline composition. It does not contain a standalone Executor artifact, real external tools, or the broader historical regression environment. Historical 45-test and 89-test claims remain historical and are not fresh evidence for this extracted package.

## Non-changes

- No existing production core, existing agency test, gateway, ConfirmationChannel source, ExecutionBoundary source, or existing test file was modified.
- `Executor` (standalone) remains **Not available**.
- Real external tools and broader end-to-end regression remain out of scope.
- No claim was made that local ToolRegistry tests prove production tool safety.
- No claim was made that all real-gate branches or production Pipeline orchestration have been tested.
- Historical documentation and preserved pytest outputs were not upgraded to fresh evidence beyond the newly executed focused suites.

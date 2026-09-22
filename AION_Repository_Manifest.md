> ## ⚠️ ARCHIVED — DO NOT USE AS CURRENT REFERENCE
>
> **Archived on:** 2026-09-22
>
> This manifest describes the pre-rename `aion-confirmation-channel`
> repository. It is preserved as historical provenance only. The files
> it references (including `AION_Architecture.md`,
> `AION_Reference_Implementation.md`, `AION_STATUS.md`,
> `REGRESSION_BASELINE.md`, and `aion/execution/executor.py`) do not
> exist in the current AION repository. Its verification summary
> ("25 passed", "GitHub Actions: not yet observed") reflects an
> earlier state and is not current.
>
> **Source of truth for current structure:** README.md
> **Source of truth for current status:** KNOWN_LIMITATIONS.md
> **Source of truth for provenance:** ORIGIN.md,
> AION_Origin_and_Provenance.md
>
> See `git log --follow AION_Repository_Manifest.md` for history.

# AION Repository Manifest

**Purpose:** Review the exact files currently prepared for the private `aion-confirmation-channel` repository.

**Generated:** 2026-09-15

## Files intended for the repository

### Documentation

- `AION_Architecture.md` — Architecture and authority-boundary description.
- `AION_Constitution.md` — Constitutional rules and normative state distinctions.
- `AION_Invariants.md` — Invariants I-1–I-9 and principles M-1–M-9.
- `AION_Reference_Implementation.md` — Reference implementation and proof-phase map.
- `AION_STATUS.md` — Current project status and provenance classification.
- `AION_Trust_Boundary_Map.md` — Trust-boundary claims and evidence mapping.
- `CHANGELOG.md` — Provenance-corrected version-level history.
- `EXTERNAL_SIGNALS.md` — Post-publication signal-to-evidence specification.
- `F_DEFECTS_EVIDENCE_CHECKLIST.md` — Evidence requirements for F-defect history.
- `REGRESSION_BASELINE.md` — Available regression evidence and limitations.
- `AION_SECURITY_FLOW_REPORT.md` — Visual MarkdownX report of the confirmation, execution, and audit flow.

### Core implementation

- `aion_core (2).py` — Original available AION Core source snapshot.
- `aion_core.py` — Import-compatible wrapper exposing the snapshot as `aion_core`.
- `aion/__init__.py` — AION package initializer.
- `aion/execution/__init__.py` — Execution package exports.
- `aion/execution/channel.py` — `ConfirmationEvent` and `ConfirmationChannel` implementation.
- `aion/execution/boundary.py` — `ExecutionBoundary` enforcement layer that binds payload verification to handler invocation.
- `aion/execution/executor.py` — Exact action/tool handler registry and dispatch layer.

### Tests and test configuration

- `conftest.py` — Existing pytest import-path configuration.
- `test_i1_to_i5_agency (1).py` — Available agency and invariant test source.
- `tests/test_replay.py` — Confirmation-scope replay tests using the local mock harness.
- `tests/test_confirmation_channel.py` — Unit tests for the real `ConfirmationChannel`.
- `tests/test_confirmation_integration.py` — Integration tests connecting the real AION Core snapshot to the real `ConfirmationChannel`.
- `tests/test_execution_boundary.py` — Integration tests for payload enforcement, replay refusal, and handler-error logging.
- `tests/test_execution_end_to_end.py` — End-to-end tests connecting `ConfirmationChannel`, `ExecutionBoundary`, and `Executor`.
- `tests/test_execution_audit.py` — Structured audit tests for allowed, refused, and handler-error outcomes.

### CI and local automation

- `.github/workflows/confirmation-scope.yml` — GitHub Actions workflow for full tests, targeted and full coverage, and Bandit scans on `push` and `pull_request`.
- `Makefile` — Local targets for tests, coverage, security scanning, and the combined `ci` pipeline.
- `extract_tests.sh` — Existing test extraction helper.
- `restore_constitution.sh` — Existing restoration helper.
- `restore_sections.sh` — Existing restoration helper.

### Evidence artifact

- `pytest_output (3).txt` — Available pytest output artifact; records the historical 45-test passing session.
- `aion-security-flow.mmd` and `aion-security-flow.png` — Editable Mermaid source and rendered security-flow diagram.

## Files intentionally excluded from the repository

The following are generated or environment-specific files and should not be committed:

- `.pytest_cache/`
- `__pycache__/`
- `tests/__pycache__/`
- `*.pyc`
- `.coverage`
- editor- or operating-system-specific temporary files.

## Current verification summary

- Full local pytest suite: **25 passed**.
- Confirmation-scope focused coverage: **100%**.
- Full branch coverage: **59%**, with a configured CI threshold of **50%**.
- ConfirmationChannel unit and integration tests: **11 passed**.
- Bandit scans: **no issues identified** after documented false-positive exclusions.
- GitHub Actions remote execution: **not yet observed** in the current session.

## Provenance note

Presence in this manifest means that the file exists in the current local project directory. It does not by itself establish that every historical claim in the file is runtime-verified. The project continues to distinguish runtime evidence, documented historical claims, and unavailable provenance.

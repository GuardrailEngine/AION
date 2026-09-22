# AION Origin and Provenance

## Purpose

This document records the provenance of the AION reference implementation. It prevents the proof phase from appearing to be the unexplained output of a single undifferentiated system after the passage of time.

## Construction model

AION was developed through an iterative human–AI collaboration. The human-directed process defined the scope, selected the proof questions, reviewed proposed structures, supplied or approved test specifications, and authorized progression between phases. The sandboxed execution environment created and modified the repository files, ran the commands, inspected the results, and preserved the resulting artifacts.

The conversational material supplied with the project included contributions from multiple model contexts, including AI-assisted specification input and automated execution and verification performed in a sandboxed environment. These contributions are recorded here as provenance, not as a claim that every model context had filesystem access or execution authority.

## Responsibility boundaries

| Responsibility | Agent or source | Repository evidence |
|---|---|---|
| Proof goals and phase decisions | Human-directed project process | Versioned test and documentation scope |
| Core and test specifications | Conversational AI contributions | `aion_core.py` and `tests/` |
| File creation, relocation, and edits | the sandboxed execution environment | Repository tree and file artifacts |
| Syntax checks and test execution | the sandboxed execution environment | `pytest_*.txt` reports |
| Final interpretation of evidence | Collaborative review | `docs/` reference set |

## Execution boundary of the provenance record

The conversational model that supplied shell instructions was not treated as an executor unless the sandboxed execution environment actually performed the corresponding filesystem operation. A textual instruction to create or move a file is not evidence that the operation occurred. The repository state and command output are the evidence of execution.

This distinction follows the same principle used by the implementation: **proposal is not execution**.

## Evidence boundary

The reference implementation records what was created and tested in this environment. It does not establish authorship of every conceptual idea, guarantee reproducibility in an unmodified environment, or claim that the tested scenarios exhaust the behavior of future models, tools, or deployments.

## References

[1]: README.md "AION Reference Implementation overview"
[2]: FROZEN_VERSIONS.md "AION frozen proof-phase versions"
[3]: ../pytest_full_v04.txt "AION v0.4 full regression report"

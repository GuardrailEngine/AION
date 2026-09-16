# AION Invariants

## Purpose

An invariant is a property that must remain true across valid executions and adversarial inputs. The proof phase defines nine primary invariants, supporting M-series principles, and runtime evidence from v2.1 through v0.4.

## Primary invariants

| ID | Invariant | Runtime evidence |
|---|---|---|
| I-1 | Agency transitions are recorded and explain the final state. | Agency tests verify transition formatting and presence. |
| I-2 | Higher risk does not increase agency. | Low- and high-risk Agency Gate comparison. |
| I-3 | Enforceable constitutional violations produce refusal and blocked execution. | Constitution and execution tests. |
| I-4 | `ACTION` never implies `EXECUTED`; it remains confirmation-gated. | Agency and execution tests. |
| I-5 | Unverified action proposals cannot become `ACTION`. | Agency and adversarial tests. |
| I-6 | Model output cannot directly grant execution authority. | Structural isolation and adversarial tests. |
| I-7 | The Safety Floor is independent of model risk minimization and intent claims. | Explicit harmful-input tests. |
| I-8 | Untrusted fields are sanitized before they influence Core state. | Enum, confidence, boolean, and injection tests. |
| I-9 | Constitutional failures and clarification states remain distinct. | Constitution and Agency Gate tests. |

## Supporting principles

| ID | Principle | Meaning |
|---|---|---|
| M-1 | The model proposes; the Core decides. | Model output is never self-authorizing. |
| M-2 | `ACTION` is not execution. | Agency classification and tool invocation are separate states. |
| M-3 | No tool call precedes the Agency Gate and execution boundary. | Tools are invoked only by the executor after checks. |
| M-4 | Confirmation is external authorization. | Textual claims cannot replace a channel event. |
| M-5 | Audit evidence must distinguish attempt from result. | Rejected attempts and tool outcomes are separate records. |
| M-6 | Safety floors are lower bounds. | A model cannot reduce critical risk by reporting low factors. |
| M-7 | Boundaries require evidence. | A claim that a limit works is insufficient without a passing test. |
| M-8 | Confidence is a signal, not authority. | High confidence cannot override insufficient evidence or policy. |
| M-9 | Longitudinal context is not authority. | Prior session state cannot create confirmation or identity. |

## Required properties for changes

Any future change to the Core or execution runtime must preserve the following properties:

1. A model-generated field cannot directly set `requires_action_verified`.
2. An `ACTION` decision cannot be treated as executed without a verified event.
3. A confirmation event cannot be reused after consumption.
4. Event, decision, and payload request identities must agree.
5. Explicit safety-floor matches cannot be downgraded by model output.
6. Audit records must preserve rejected attempts and execution results separately.
7. Longitudinal context must remain outside production authority paths unless a new capability is explicitly designed and tested.

## References

[1]: ../aion_core.py "AION Core v2.1 implementation"
[2]: ../aion/execution/boundary.py "AION execution boundary"
[3]: ../aion/execution/channel.py "AION confirmation channel"
[4]: ../pytest_full_v04.txt "AION v0.4 full regression report"

"""Execution boundary for AION.

The current repository has no trusted external-approval verifier and no
atomic compare-and-execute handler contract. This boundary therefore validates
issuance and scope but fails closed before every tool dispatch.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aion.execution.channel import ConfirmationChannel, ConfirmationEvent


@dataclass
class ExecutionResult:
    executed: bool
    reason: str
    payload: Any | None = None


class ToolRegistry:
    """Registry of tools available to the execution boundary."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[[Any], Any]] = {}

    def register(self, name: str, fn: Callable[[Any], Any]) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = fn

    def get(self, name: str) -> Callable[[Any], Any]:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools


class ExecutionBoundary:
    """Validate event provenance and scope, then refuse unsupported dispatch.

    A channel-issued event is not evidence of external user approval. No trusted
    approval verifier exists in this repository, and filesystem snapshotting is
    not atomic with arbitrary tool calls. Consequently, this implementation
    never invokes a registered tool: target-bound events fail because atomic
    compare-and-execute is unavailable; unbound events fail because external
    approval cannot be verified.
    """

    def __init__(
        self,
        channel: ConfirmationChannel,
        registry: ToolRegistry,
        target_authority: Any | None = None,
    ) -> None:
        self.channel = channel
        self.registry = registry
        self.target_authority = target_authority

    @staticmethod
    def _target_identity(target_ref: Any) -> str | None:
        identity = getattr(target_ref, "path", None)
        if isinstance(identity, str) and identity:
            return identity
        return None

    def execute(
        self,
        event: ConfirmationEvent,
        action: str,
        tool: str,
        session_id: str,
        payload: Any,
        *,
        target_ref: Any | None = None,
    ) -> ExecutionResult:
        if not isinstance(event, ConfirmationEvent) or not self.channel._owns_event(event):
            return ExecutionResult(False, "unissued_confirmation")
        if self.channel._is_consumed(event):
            return ExecutionResult(False, "already_used")
        if not self.registry.has(tool):
            return ExecutionResult(False, "unknown_tool")

        target_values = (
            event.target_ref,
            event.target_version,
            event.target_hash,
        )
        target_is_bound = any(value is not None for value in target_values)
        current_target_ref = None
        current_target_version = None
        current_target_hash = None

        if target_is_bound:
            if not all(
                isinstance(value, str) and value.strip()
                for value in target_values
            ):
                return ExecutionResult(False, "target_binding_incomplete")
            if target_ref is None:
                return ExecutionResult(False, "target_ref_required")
            if self.target_authority is None:
                return ExecutionResult(False, "target_authority_required")
            current_target_ref = self._target_identity(target_ref)
            if current_target_ref is None:
                return ExecutionResult(False, "target_ref_invalid")
            if current_target_ref != event.target_ref:
                return ExecutionResult(False, "target_ref_mismatch")

            try:
                snapshot = self.target_authority.snapshot(action, target_ref)
            except FileNotFoundError:
                return ExecutionResult(False, "target_not_found")
            # Any authority failure aborts this request; dispatch never follows.
            except Exception:  # noqa: BLE001
                return ExecutionResult(False, "target_authority_error")

            snapshot_ref = self._target_identity(getattr(snapshot, "target_ref", None))
            if snapshot_ref is None:
                return ExecutionResult(False, "target_authority_invalid")
            if snapshot_ref != event.target_ref:
                return ExecutionResult(False, "target_ref_mismatch")
            current_target_version = getattr(snapshot, "version", None)
            current_target_hash = getattr(snapshot, "content_hash", None)
            if not all(
                isinstance(value, str) and value.strip()
                for value in (current_target_version, current_target_hash)
            ):
                return ExecutionResult(False, "target_state_unavailable")
        elif target_ref is not None:
            return ExecutionResult(False, "target_binding_mismatch")

        valid, reason = self.channel.verify(
            event=event,
            action=action,
            tool=tool,
            session_id=session_id,
            payload=payload,
            current_target_ref=current_target_ref,
            current_target_version=current_target_version,
            current_target_hash=current_target_hash,
            request_id=event.request_id,
        )
        if not valid:
            return ExecutionResult(False, reason)

        if target_is_bound:
            return ExecutionResult(False, "atomic_target_execution_unavailable")
        return ExecutionResult(False, "external_approval_unavailable")

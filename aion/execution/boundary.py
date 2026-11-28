"""Execution boundary for AION.

The default boundary remains fail-closed. A separate test-only path supports
one explicitly injected local approval simulator and one SQLite target
provider; it never dispatches a registered tool handler.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aion.execution.channel import ConfirmationChannel, ConfirmationEvent
from aion.execution.local_test_approval import (
    ApprovalReceipt,
    LocalTestApprovalProvider,
)
from aion.target.sqlite_authority import SqliteTargetProvider, SqliteTargetRef


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
    """Validate event provenance and refuse every unsupported dispatch.

    Only an exact ``LocalTestApprovalProvider`` + ``SqliteTargetProvider`` pair
    can enter the test path, and both providers independently require
    ``AION_ENV=test``. That path performs the fixed SQLite operation directly
    and never calls a tool registered in ``ToolRegistry``.
    """

    def __init__(
        self,
        channel: ConfirmationChannel,
        registry: ToolRegistry,
        target_authority: Any | None = None,
        approval_provider: Any | None = None,
    ) -> None:
        self.channel = channel
        self.registry = registry
        self.target_authority = target_authority
        self.approval_provider = approval_provider

    @staticmethod
    def _target_identity(target_ref: Any) -> str | None:
        identity = getattr(target_ref, "identity", None)
        if isinstance(identity, str) and identity:
            return identity
        identity = getattr(target_ref, "path", None)
        if isinstance(identity, str) and identity:
            return identity
        return None

    def _execute_sqlite_test_path(
        self,
        event: ConfirmationEvent,
        action: str,
        tool: str,
        session_id: str,
        payload: Any,
        target_ref: Any,
        approval_receipt: ApprovalReceipt | None,
    ) -> ExecutionResult:
        if type(self.target_authority) is not SqliteTargetProvider:
            return ExecutionResult(False, "atomic_target_execution_unavailable")
        if type(self.approval_provider) is not LocalTestApprovalProvider:
            return ExecutionResult(False, "external_approval_unavailable")
        if approval_receipt is None:
            return ExecutionResult(False, "external_approval_unavailable")
        if action != event.action:
            return ExecutionResult(False, "action_mismatch")
        if tool != event.tool:
            return ExecutionResult(False, "tool_mismatch")
        if session_id != event.session_id:
            return ExecutionResult(False, "session_mismatch")
        if type(target_ref) is not SqliteTargetRef:
            return ExecutionResult(False, "atomic_target_execution_unavailable")
        if (
            self.target_authority.database_identity
            == self.approval_provider.store_identity
        ):
            return ExecutionResult(False, "external_approval_unavailable")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (event.target_ref, event.target_version, event.target_hash)
        ) or event.expected_generation is None:
            return ExecutionResult(False, "target_binding_incomplete")
        target_identity = self.target_authority.identity(target_ref)
        if target_identity is None:
            return ExecutionResult(False, "target_ref_invalid")
        if target_identity != event.target_ref:
            return ExecutionResult(False, "target_ref_mismatch")

        event_was_consumed = self.channel._is_consumed(event)
        if not event_was_consumed:
            try:
                snapshot = self.target_authority.snapshot(action, target_ref)
            except FileNotFoundError:
                return ExecutionResult(False, "target_not_found")
            except Exception:  # noqa: BLE001
                return ExecutionResult(False, "atomic_target_execution_unavailable")
            valid, reason = self.channel.verify(
                event=event,
                action=action,
                tool=tool,
                session_id=session_id,
                payload=payload,
                current_target_ref=target_identity,
                current_target_version=snapshot.version,
                current_target_hash=snapshot.content_hash,
                current_expected_generation=snapshot.generation,
                request_id=event.request_id,
            )
            if not valid:
                return ExecutionResult(False, reason)

        try:
            outcome = self.target_authority.compare_and_update(
                approval_provider=self.approval_provider,
                event=event,
                receipt=approval_receipt,
                payload=payload,
                target_ref=target_ref,
                event_was_consumed=event_was_consumed,
            )
        except Exception:  # noqa: BLE001
            return ExecutionResult(False, "atomic_target_execution_unavailable")
        if not outcome.executed:
            return ExecutionResult(False, outcome.reason)

        # The signed receipt is the authorization; this event remains request
        # context. Mark it consumed after the committed target result where
        # possible, without changing a successfully committed outcome.
        if not self.channel._is_consumed(event):
            self.channel.verify_and_consume(
                event=event,
                action=action,
                tool=tool,
                session_id=session_id,
                payload=payload,
                current_target_ref=event.target_ref,
                current_target_version=event.target_version,
                current_target_hash=event.target_hash,
                current_expected_generation=event.expected_generation,
                request_id=event.request_id,
            )
        return ExecutionResult(True, outcome.reason, outcome.payload)

    def execute(
        self,
        event: ConfirmationEvent,
        action: str,
        tool: str,
        session_id: str,
        payload: Any,
        *,
        target_ref: Any | None = None,
        approval_receipt: ApprovalReceipt | None = None,
    ) -> ExecutionResult:
        if not isinstance(event, ConfirmationEvent) or not self.channel._owns_event(event):
            return ExecutionResult(False, "unissued_confirmation")
        if not self.registry.has(tool):
            return ExecutionResult(False, "unknown_tool")

        target_values = (
            event.target_ref,
            event.target_version,
            event.target_hash,
        )
        target_is_bound = any(value is not None for value in target_values) or (
            event.expected_generation is not None
        )

        if target_is_bound and type(self.target_authority) is SqliteTargetProvider:
            if target_ref is None:
                return ExecutionResult(False, "target_ref_required")
            return self._execute_sqlite_test_path(
                event,
                action,
                tool,
                session_id,
                payload,
                target_ref,
                approval_receipt,
            )

        current_target_ref = None
        current_target_version = None
        current_target_hash = None
        current_expected_generation = None

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
            current_expected_generation = getattr(snapshot, "generation", None)
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
            current_expected_generation=current_expected_generation,
            request_id=event.request_id,
        )
        if not valid:
            return ExecutionResult(False, reason)

        if target_is_bound:
            return ExecutionResult(False, "atomic_target_execution_unavailable")
        return ExecutionResult(False, "external_approval_unavailable")

"""Execution boundary — enforces confirmation before any sensitive action is executed."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aion.binding import TracingRow, detect_binding_drift, get_binding
from aion.execution.channel import (
    ConfirmationChannel,
    ConfirmationEvent,
)


@dataclass
class ExecutionResult:
    executed: bool
    reason: str
    payload: Any | None = None


class ToolRegistry:
    """Registry of tools that can be executed."""

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
    """Enforces confirmation binding before executing a tool.

    The boundary does NOT trust the caller. It re-verifies the
    confirmation against the payload that is about to be executed,
    then consumes it, then dispatches to the tool.
    """

    def __init__(
        self,
        channel: ConfirmationChannel,
        registry: ToolRegistry,
    ) -> None:
        self.channel = channel
        self.registry = registry

    def _record_binding_drift(self, event: ConfirmationEvent, action: str, finding: dict) -> None:
        """Record Phase A binding drift in the channel's existing audit sink."""
        self.channel._audit.append({
            "event": "binding_drift",
            "layer": "binding_drift",
            "request_id": event.request_id,
            "action": action,
            "undeclared_fields": finding["undeclared_fields"],
            "unused_fields": finding["unused_fields"],
            "risk": finding["severity"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def execute(
        self,
        event: ConfirmationEvent,
        action: str,
        tool: str,
        session_id: str,
        payload: Any,
    ) -> ExecutionResult:
        if not self.registry.has(tool):
            return ExecutionResult(
                executed=False,
                reason="unknown_tool",
            )

        valid, reason = self.channel.verify_and_consume(
            event=event,
            action=action,
            tool=tool,
            session_id=session_id,
            payload=payload,
        )

        if not valid:
            return ExecutionResult(executed=False, reason=reason)

        tool_fn = self.registry.get(tool)
        execution_payload = payload
        traced_payload = None
        if isinstance(payload, dict):
            traced_payload = TracingRow(payload)
            execution_payload = traced_payload
        try:
            result = tool_fn(execution_payload)
        except (RuntimeError, ValueError, TypeError) as exc:
            if traced_payload is not None:
                finding = detect_binding_drift(
                    traced_payload.accessed_fields,
                    get_binding(action),
                )
                if finding is not None:
                    self._record_binding_drift(event, action, finding)
            return ExecutionResult(
                executed=False,
                reason=f"tool_error: {type(exc).__name__}",
            )

        if traced_payload is not None:
            finding = detect_binding_drift(
                traced_payload.accessed_fields,
                get_binding(action),
            )
            if finding is not None:
                self._record_binding_drift(event, action, finding)

        return ExecutionResult(
            executed=True,
            reason="ok",
            payload=result,
        )

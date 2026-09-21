"""Action-aware target binding definitions for AION."""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class ActionBinding:
    """Declare which target fields an action binds to."""

    action: str
    fields: tuple[str, ...]
    description: str = ""

    def is_full_row(self) -> bool:
        return self.fields == ("*",)

    def __post_init__(self) -> None:
        if not self.action:
            raise ValueError("action must be a non-empty string")
        if not self.fields:
            raise ValueError("fields must be non-empty; use ('*',) for full-row")
        if "*" in self.fields and self.fields != ("*",):
            raise ValueError("'*' must be the only element if present")


DEFAULT_BINDINGS: dict[str, ActionBinding] = {
    "delete_file": ActionBinding(
        action="delete_file",
        fields=("path", "content_hash"),
        description="Binds to file path and content hash.",
    ),
    "update_profile": ActionBinding(
        action="update_profile",
        fields=("*",),
        description="Binds to full user row.",
    ),
    "read_file": ActionBinding(
        action="read_file",
        fields=("path",),
        description="Reads only path.",
    ),
}


def register_binding(binding: ActionBinding) -> None:
    """Register or replace a binding for an action."""
    DEFAULT_BINDINGS[binding.action] = binding


def get_binding(action: str) -> ActionBinding:
    """Return a binding, using a fail-safe full-row default."""
    binding = DEFAULT_BINDINGS.get(action)
    if binding is not None:
        return binding
    return ActionBinding(
        action=action,
        fields=("*",),
        description="Implicit full-row (no explicit binding registered).",
    )

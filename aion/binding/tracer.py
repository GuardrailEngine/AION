"""Field tracing for detecting action binding drift."""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from aion.binding.definition import ActionBinding


class TracingRow(Mapping[str, Any]):
    """Read-only mapping wrapper that records field accesses."""

    def __init__(self, row: Mapping[str, Any]) -> None:
        if not isinstance(row, Mapping):
            raise TypeError("row must be a mapping")
        self._row = row
        self._accessed: set[str] = set()

    def __getitem__(self, key: str) -> Any:
        self._accessed.add(key)
        return self._row[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._row)

    def __len__(self) -> int:
        return len(self._row)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            self._accessed.add(key)
        return key in self._row

    def get(self, key: str, default: Any = None) -> Any:
        if isinstance(key, str):
            self._accessed.add(key)
        return self._row.get(key, default)

    def keys(self):
        """Return keys without counting key enumeration as field reads."""
        return self._row.keys()

    @property
    def accessed_fields(self) -> frozenset[str]:
        return frozenset(self._accessed)

    def reset(self) -> None:
        self._accessed.clear()


def observed_vs_declared(
    observed: frozenset[str],
    binding: ActionBinding,
) -> dict[str, list[str]]:
    """Return undeclared and unused fields for an observed action run."""
    if binding.is_full_row():
        return {"undeclared": [], "unused": []}

    declared = set(binding.fields)
    return {
        "undeclared": sorted(set(observed) - declared),
        "unused": sorted(declared - set(observed)),
    }


def detect_binding_drift(
    observed: frozenset[str],
    binding: ActionBinding,
) -> dict[str, Any] | None:
    """Return a HIGH-severity finding when undeclared fields were read."""
    diff = observed_vs_declared(observed, binding)
    if not diff["undeclared"]:
        return None
    return {
        "action": binding.action,
        "undeclared_fields": diff["undeclared"],
        "unused_fields": diff["unused"],
        "severity": "HIGH",
    }

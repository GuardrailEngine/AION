"""Compute target hashes according to action bindings."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aion.binding.definition import ActionBinding
from aion.execution.channel import hash_payload


def hash_row_by_binding(row: Mapping[str, Any], binding: ActionBinding) -> str:
    """Hash a target row using only the fields declared by the binding."""
    if not isinstance(row, Mapping):
        raise TypeError("row must be a mapping")

    if binding.is_full_row():
        selected: dict[str, Any] = dict(row)
    else:
        missing = [field for field in binding.fields if field not in row]
        if missing:
            raise ValueError(
                f"binding for action '{binding.action}' requires "
                f"fields {list(binding.fields)}; missing: {missing}"
            )
        selected = {field: row[field] for field in binding.fields}

    return hash_payload(selected)

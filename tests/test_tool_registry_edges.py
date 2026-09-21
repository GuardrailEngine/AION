"""Edge-case tests for ToolRegistry's explicit error contracts."""
from __future__ import annotations

import pytest

from aion.execution.boundary import ToolRegistry


def test_register_duplicate_tool_name_raises_value_error():
    registry = ToolRegistry()
    registry.register("filesystem", lambda payload: payload)

    with pytest.raises(ValueError, match="Tool already registered: filesystem"):
        registry.register("filesystem", lambda payload: payload)


def test_get_unknown_tool_raises_key_error():
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="Unknown tool: missing_tool"):
        registry.get("missing_tool")

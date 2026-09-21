"""Unit tests for the AION Target Binding Layer."""
from __future__ import annotations

import pytest

from aion.binding import (
    ActionBinding,
    get_binding,
    hash_row_by_binding,
    register_binding,
)


def test_full_row_hash_rejects_unrelated_change():
    binding = ActionBinding(action="x", fields=("*",))
    row_v1 = {"path": "a.txt", "size": 1, "last_accessed": 100}
    row_v2 = {"path": "a.txt", "size": 1, "last_accessed": 200}
    assert hash_row_by_binding(row_v1, binding) != hash_row_by_binding(row_v2, binding)


def test_relevant_fields_accept_unrelated_change():
    binding = ActionBinding(action="delete_file", fields=("path", "content_hash"))
    row_v1 = {"path": "a.txt", "content_hash": "abc", "size": 100}
    row_v2 = {"path": "a.txt", "content_hash": "abc", "size": 999}
    assert hash_row_by_binding(row_v1, binding) == hash_row_by_binding(row_v2, binding)


def test_relevant_fields_reject_relevant_change():
    binding = ActionBinding(action="delete_file", fields=("path", "content_hash"))
    row_v1 = {"path": "a.txt", "content_hash": "abc"}
    row_v2 = {"path": "a.txt", "content_hash": "def"}
    assert hash_row_by_binding(row_v1, binding) != hash_row_by_binding(row_v2, binding)


def test_binding_is_action_specific():
    delete = get_binding("delete_file")
    update = get_binding("update_profile")
    read = get_binding("read_file")
    assert delete.fields != update.fields
    assert delete.fields != read.fields
    assert update.fields != read.fields


def test_default_is_full_row_when_binding_missing():
    assert get_binding("totally_unknown_action_xyz").is_full_row()


def test_missing_bound_field_raises():
    binding = ActionBinding(action="delete_file", fields=("path", "content_hash"))
    with pytest.raises(ValueError, match="missing"):
        hash_row_by_binding({"path": "a.txt"}, binding)


def test_non_mapping_row_raises():
    binding = ActionBinding(action="x", fields=("a",))
    with pytest.raises(TypeError):
        hash_row_by_binding(["not", "a", "mapping"], binding)


def test_binding_requires_non_empty_action():
    with pytest.raises(ValueError):
        ActionBinding(action="", fields=("a",))


def test_binding_requires_non_empty_fields():
    with pytest.raises(ValueError):
        ActionBinding(action="x", fields=())


def test_binding_rejects_mixed_wildcard():
    with pytest.raises(ValueError):
        ActionBinding(action="x", fields=("*", "path"))


def test_registered_binding_overrides_default():
    register_binding(ActionBinding(action="custom_action", fields=("id",)))
    assert get_binding("custom_action").fields == ("id",)

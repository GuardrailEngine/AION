"""Tests for field tracing and binding drift detection."""
from __future__ import annotations

import pytest

from aion.binding import (
    ActionBinding,
    TracingRow,
    detect_binding_drift,
    observed_vs_declared,
)


def test_tracing_row_records_getitem():
    traced = TracingRow({"path": "a.txt", "size": 100})
    _ = traced["path"]
    _ = traced["size"]
    assert traced.accessed_fields == frozenset({"path", "size"})


def test_tracing_row_records_get_method():
    traced = TracingRow({"path": "a.txt", "size": 100})
    _ = traced.get("path")
    _ = traced.get("missing", default=0)
    assert traced.accessed_fields == frozenset({"path", "missing"})


def test_tracing_row_records_contains():
    traced = TracingRow({"path": "a.txt"})
    _ = "path" in traced
    _ = "size" in traced
    assert traced.accessed_fields == frozenset({"path", "size"})


def test_tracing_row_does_not_count_iteration_or_len():
    traced = TracingRow({"a": 1, "b": 2})
    _ = len(traced)
    _ = list(iter(traced))
    assert traced.accessed_fields == frozenset()


def test_tracing_row_mapping_interface():
    traced = TracingRow({"path": "a.txt"})
    assert "path" in traced
    assert traced["path"] == "a.txt"
    assert len(traced) == 1


def test_tracing_row_rejects_non_mapping():
    with pytest.raises(TypeError):
        TracingRow(["not", "a", "mapping"])


def test_tracing_row_reset():
    traced = TracingRow({"path": "a.txt"})
    _ = traced["path"]
    assert traced.accessed_fields == frozenset({"path"})
    traced.reset()
    assert traced.accessed_fields == frozenset()


def test_tracing_row_does_not_mutate_underlying():
    row = {"path": "a.txt", "size": 100}
    snapshot = dict(row)
    traced = TracingRow(row)
    _ = traced["path"]
    _ = traced.get("size")
    _ = "missing" in traced
    assert dict(row) == snapshot


def test_no_drift_when_only_declared_fields_read():
    binding = ActionBinding(action="delete_file", fields=("path", "content_hash"))
    assert detect_binding_drift(
        frozenset({"path", "content_hash"}), binding
    ) is None


def test_drift_when_undeclared_field_read():
    binding = ActionBinding(action="delete_file", fields=("path", "content_hash"))
    finding = detect_binding_drift(
        frozenset({"path", "content_hash", "owner"}), binding
    )
    assert finding is not None
    assert finding["action"] == "delete_file"
    assert finding["undeclared_fields"] == ["owner"]
    assert finding["severity"] == "HIGH"


def test_full_row_binding_never_drifts():
    binding = ActionBinding(action="update_profile", fields=("*",))
    assert detect_binding_drift(frozenset({"anything", "goes", "here"}), binding) is None


def test_unused_declared_fields_are_reported():
    binding = ActionBinding(action="delete_file", fields=("path", "content_hash"))
    diff = observed_vs_declared(frozenset({"path"}), binding)
    assert diff["undeclared"] == []
    assert diff["unused"] == ["content_hash"]


def test_observed_vs_declared_full_row_returns_empty():
    binding = ActionBinding(action="update_profile", fields=("*",))
    assert observed_vs_declared(frozenset({"a", "b"}), binding) == {
        "undeclared": [],
        "unused": [],
    }


def test_drift_ordering_is_stable():
    binding = ActionBinding(action="delete_file", fields=("path",))
    finding = detect_binding_drift(
        frozenset({"z_field", "a_field", "m_field"}), binding
    )
    assert finding["undeclared_fields"] == ["a_field", "m_field", "z_field"]


def test_tracing_row_feeds_drift_detection():
    binding = ActionBinding(action="delete_file", fields=("path",))
    traced = TracingRow({"path": "a.txt", "content_hash": "abc", "owner": "alice"})
    _ = traced["path"]
    _ = traced["content_hash"]
    finding = detect_binding_drift(traced.accessed_fields, binding)
    assert finding is not None
    assert finding["undeclared_fields"] == ["content_hash"]

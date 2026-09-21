"""Runtime seam test: tracer, drift detection, and audit-only policy."""
from __future__ import annotations

from aion.binding import (
    ActionBinding,
    TracingRow,
    detect_binding_drift,
    get_binding,
    register_binding,
)


def traced_execution(action_name, row, action_fn):
    """Run an action against a TracingRow and return its drift finding."""
    binding = get_binding(action_name)
    traced = TracingRow(row)
    result = action_fn(traced)
    observed = traced.accessed_fields
    drift = detect_binding_drift(observed, binding)
    return result, observed, drift


class AuditLog:
    """Minimal audit sink for the Phase A observe-only seam."""

    def __init__(self):
        self.records = []

    def record_drift(self, finding, request_id):
        if finding is None:
            return
        self.records.append({
            "layer": "binding_drift",
            "message": (
                f"action '{finding['action']}' read undeclared fields: "
                f"{finding['undeclared_fields']}"
            ),
            "risk": finding["severity"],
            "request_id": request_id,
            "undeclared_fields": finding["undeclared_fields"],
        })


def test_declared_fields_only_no_drift_and_audit_is_empty():
    register_binding(ActionBinding(
        action="seam_clean_action",
        fields=("path", "content_hash"),
    ))
    row = {"path": "a.txt", "content_hash": "abc", "size": 100}
    audit = AuditLog()

    def clean_action(traced_row):
        return {"path": traced_row["path"], "hash": traced_row["content_hash"]}

    result, observed, drift = traced_execution("seam_clean_action", row, clean_action)
    audit.record_drift(drift, request_id="req-1")

    assert result == {"path": "a.txt", "hash": "abc"}
    assert observed == frozenset({"path", "content_hash"})
    assert drift is None
    assert audit.records == []


def test_undeclared_field_read_surfaces_high_drift_and_reaches_audit():
    register_binding(ActionBinding(
        action="seam_drift_action",
        fields=("path", "content_hash"),
    ))
    row = {"path": "a.txt", "content_hash": "abc", "owner": "alice", "size": 100}
    audit = AuditLog()

    def drifting_action(traced_row):
        return {
            "path": traced_row["path"],
            "hash": traced_row["content_hash"],
            "owner": traced_row["owner"],
        }

    result, observed, drift = traced_execution(
        "seam_drift_action", row, drifting_action
    )
    audit.record_drift(drift, request_id="req-2")

    assert result["owner"] == "alice"
    assert observed == frozenset({"path", "content_hash", "owner"})
    assert drift is not None
    assert drift["severity"] == "HIGH"
    assert drift["undeclared_fields"] == ["owner"]
    assert len(audit.records) == 1
    record = audit.records[0]
    assert record["layer"] == "binding_drift"
    assert record["risk"] == "HIGH"
    assert record["undeclared_fields"] == ["owner"]
    assert record["request_id"] == "req-2"
    assert "owner" in record["message"]


def test_full_row_binding_never_drifts_even_with_extra_reads():
    register_binding(ActionBinding(action="seam_full_row_action", fields=("*",)))
    row = {"a": 1, "b": 2, "c": 3}
    audit = AuditLog()

    def broad_action(traced_row):
        return {key: traced_row[key] for key in ("a", "b", "c")}

    result, observed, drift = traced_execution(
        "seam_full_row_action", row, broad_action
    )
    audit.record_drift(drift, request_id="req-3")

    assert result == row
    assert observed == frozenset({"a", "b", "c"})
    assert drift is None
    assert audit.records == []


def test_execution_is_not_blocked_on_high_drift():
    register_binding(ActionBinding(action="seam_phase_a_action", fields=("path",)))
    row = {"path": "a.txt", "secret_field": "leaked"}
    audit = AuditLog()

    def action_that_returns_value(traced_row):
        return traced_row["secret_field"]

    result, observed, drift = traced_execution(
        "seam_phase_a_action", row, action_that_returns_value
    )
    audit.record_drift(drift, request_id="req-4")

    assert result == "leaked"
    assert observed == frozenset({"secret_field"})
    assert drift is not None
    assert drift["severity"] == "HIGH"
    assert len(audit.records) == 1


def test_drift_signal_survives_multiple_reads_of_same_field():
    register_binding(ActionBinding(action="seam_dup_action", fields=("path",)))
    row = {"path": "a.txt", "extra": "x"}
    audit = AuditLog()

    def dup_action(traced_row):
        _ = traced_row["extra"]
        _ = traced_row["extra"]

    _, observed, drift = traced_execution("seam_dup_action", row, dup_action)
    audit.record_drift(drift, request_id="req-5")

    assert observed == frozenset({"extra"})
    assert drift is not None
    assert drift["undeclared_fields"] == ["extra"]
    assert len(audit.records) == 1


def test_audit_record_shape_matches_confirmation_channel_conventions():
    register_binding(ActionBinding(action="seam_shape_action", fields=("path",)))
    row = {"path": "a.txt", "extra": "x"}
    audit = AuditLog()

    def action(traced_row):
        return traced_row["extra"]

    _, _, drift = traced_execution("seam_shape_action", row, action)
    audit.record_drift(drift, request_id="req-shape")

    record = audit.records[0]
    for key in ("layer", "message", "risk", "request_id"):
        assert key in record
    assert record["risk"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

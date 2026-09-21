"""Seam tests proving Target Binding is used by ConfirmationChannel."""
from __future__ import annotations

from aion.binding import (
    ActionBinding,
    get_binding,
    hash_row_by_binding,
    register_binding,
)
from aion.execution.channel import ConfirmationChannel


def _issue_for_row(channel, action, payload, row, binding):
    bound_hash = hash_row_by_binding(row, binding)
    return channel.issue(
        action=action,
        tool="fs",
        session_id="s1",
        payload=payload,
        target_hash=bound_hash,
    )


def _verify_against_row(channel, event, action, payload, row, binding):
    current_hash = hash_row_by_binding(row, binding)
    return channel.verify(
        event=event,
        action=action,
        tool="fs",
        session_id="s1",
        payload=payload,
        current_target_hash=current_hash,
    )


def test_bound_hash_accepted_when_target_unchanged():
    register_binding(ActionBinding(action="seam_delete", fields=("path", "content_hash")))
    binding = get_binding("seam_delete")
    channel = ConfirmationChannel()
    row = {"path": "a.txt", "content_hash": "abc", "size": 100}
    payload = {"path": "a.txt"}
    event = _issue_for_row(channel, "seam_delete", payload, row, binding)
    valid, reason = _verify_against_row(channel, event, "seam_delete", payload, row, binding)
    assert valid is True
    assert reason == "ok"


def test_irrelevant_change_accepted_via_binding():
    register_binding(ActionBinding(action="seam_irrelevant", fields=("path", "content_hash")))
    binding = get_binding("seam_irrelevant")
    channel = ConfirmationChannel()
    row_v1 = {"path": "a.txt", "content_hash": "abc", "size": 100}
    row_v2 = {"path": "a.txt", "content_hash": "abc", "size": 999}
    payload = {"path": "a.txt"}
    event = _issue_for_row(channel, "seam_irrelevant", payload, row_v1, binding)
    valid, reason = _verify_against_row(
        channel, event, "seam_irrelevant", payload, row_v2, binding
    )
    assert valid is True
    assert reason == "ok"


def test_relevant_change_rejected_via_binding():
    register_binding(ActionBinding(action="seam_relevant", fields=("path", "content_hash")))
    binding = get_binding("seam_relevant")
    channel = ConfirmationChannel()
    row_v1 = {"path": "a.txt", "content_hash": "abc"}
    row_v2 = {"path": "a.txt", "content_hash": "def"}
    payload = {"path": "a.txt"}
    event = _issue_for_row(channel, "seam_relevant", payload, row_v1, binding)
    valid, reason = _verify_against_row(
        channel, event, "seam_relevant", payload, row_v2, binding
    )
    assert valid is False
    assert reason == "target_hash_mismatch"


def test_unbound_action_uses_full_row():
    binding = get_binding("seam_unregistered_xyz")
    assert binding.is_full_row() is True
    channel = ConfirmationChannel()
    row_v1 = {"path": "a.txt", "size": 100}
    row_v2 = {"path": "a.txt", "size": 999}
    payload = {"path": "a.txt"}
    event = _issue_for_row(channel, "seam_unregistered_xyz", payload, row_v1, binding)
    valid, reason = _verify_against_row(
        channel, event, "seam_unregistered_xyz", payload, row_v2, binding
    )
    assert valid is False
    assert reason == "target_hash_mismatch"


def test_bound_hash_does_not_bypass_payload_binding():
    register_binding(ActionBinding(action="seam_payload", fields=("path", "content_hash")))
    binding = get_binding("seam_payload")
    channel = ConfirmationChannel()
    row = {"path": "a.txt", "content_hash": "abc"}
    event = _issue_for_row(channel, "seam_payload", {"path": "a.txt"}, row, binding)
    valid, reason = _verify_against_row(
        channel, event, "seam_payload", {"path": "b.txt"}, row, binding
    )
    assert valid is False
    assert reason == "payload_mismatch"

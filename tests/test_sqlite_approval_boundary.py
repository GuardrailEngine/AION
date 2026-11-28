from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from aion.execution.boundary import ExecutionBoundary, ToolRegistry
from aion.execution.channel import ConfirmationChannel
from aion.execution.local_test_approval import (
    ApprovalError,
    LocalTestApprovalProvider,
)
from aion.target.sqlite_authority import SqliteTargetProvider


def _canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _seed_resource(provider, resource_id="resource-1", value=None, *, generation=1):
    if value is None:
        value = {"status": "initial"}
    value_json = _canonical_json(value)
    content_hash = hashlib.sha256(value_json.encode("utf-8")).hexdigest()
    connection = sqlite3.connect(provider.database_path)
    try:
        connection.execute(
            "INSERT INTO aion_resources "
            "(resource_id, generation, version, value_json, content_hash) "
            "VALUES (?, ?, 1, ?, ?)",
            (resource_id, generation, value_json, content_hash),
        )
        connection.commit()
    finally:
        connection.close()


def _read_resource(provider, resource_id="resource-1"):
    connection = sqlite3.connect(provider.database_path)
    try:
        return connection.execute(
            "SELECT generation, version, value_json, content_hash "
            "FROM aion_resources WHERE resource_id = ?",
            (resource_id,),
        ).fetchone()
    finally:
        connection.close()


@pytest.fixture

def stack(tmp_path, monkeypatch):
    monkeypatch.setenv("AION_ENV", "test")
    target = SqliteTargetProvider(tmp_path / "target.sqlite")
    _seed_resource(target)
    approvals = LocalTestApprovalProvider(tmp_path / "approval-jti.sqlite")
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    handler_calls = []
    registry.register("sqlite_target", lambda data: handler_calls.append(data))
    boundary = ExecutionBoundary(
        channel,
        registry,
        target_authority=target,
        approval_provider=approvals,
    )
    return {
        "approvals": approvals,
        "boundary": boundary,
        "channel": channel,
        "handler_calls": handler_calls,
        "target": target,
        "target_ref": target.ref("resource-1"),
    }


def _request(stack, value, *, resource_id="resource-1"):
    target = stack["target"]
    target_ref = target.ref(resource_id)
    snapshot = target.snapshot(SqliteTargetProvider.ACTION, target_ref)
    payload = {"value": value}
    event = stack["channel"].issue(
        action=SqliteTargetProvider.ACTION,
        tool=SqliteTargetProvider.TOOL,
        session_id="session-1",
        payload=payload,
        target_ref=target_ref.identity,
        target_version=snapshot.version,
        target_hash=snapshot.content_hash,
        expected_generation=snapshot.generation,
    )
    receipt = stack["approvals"].issue_test_approval(event, payload)
    return event, receipt, payload, target_ref


def _execute(stack, request):
    event, receipt, payload, target_ref = request
    return stack["boundary"].execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload,
        target_ref=target_ref,
        approval_receipt=receipt,
    )


def test_valid_receipt_updates_one_row_and_never_calls_registered_handler(stack):
    request = _request(stack, {"status": "approved"})
    event, receipt, _, _ = request

    result = _execute(stack, request)

    assert result.executed is True
    assert result.reason == "ok"
    assert result.payload["request_id"] == event.request_id
    assert result.payload["version"] == 2
    assert receipt.signed_claims()["aion.confirmation_event_id"] == event.request_id
    row = _read_resource(stack["target"])
    assert row[0:2] == (1, 2)
    assert json.loads(row[2]) == {"status": "approved"}
    assert row[3] == result.payload["content_hash"]
    assert stack["handler_calls"] == []
    assert stack["channel"]._is_consumed(event)
    assert stack["target"].database_identity != stack["approvals"].store_identity


def test_same_request_id_and_receipt_return_saved_result_without_second_update(stack):
    request = _request(stack, {"status": "approved"})

    first = _execute(stack, request)
    second = _execute(stack, request)

    assert first.executed is True
    assert second.executed is True
    assert second.payload == first.payload
    assert _read_resource(stack["target"])[1] == 2
    assert stack["handler_calls"] == []


def test_replayed_receipt_for_a_different_request_cannot_mutate_target(stack):
    first_request = _request(stack, {"status": "one"})
    second_request = _request(stack, {"status": "two"})
    assert _execute(stack, first_request).executed is True

    result = _execute(stack, second_request)

    assert result.executed is False
    assert result.reason == "target_drift"
    assert _read_resource(stack["target"])[1] == 2
    assert stack["handler_calls"] == []


def test_receipt_signature_and_confirmation_event_binding_are_enforced(stack):
    request = _request(stack, {"status": "approved"})
    event, receipt, payload, target_ref = request
    forged = replace(receipt, confirmation_event_id="another-event")

    result = stack["boundary"].execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload,
        target_ref=target_ref,
        approval_receipt=forged,
    )

    assert result.executed is False
    assert result.reason == "approval_signature_invalid"
    assert _read_resource(stack["target"])[1] == 1
    assert stack["handler_calls"] == []


def test_receipt_for_another_confirmation_event_is_rejected(stack):
    first = _request(stack, {"status": "approved"})
    second = _request(stack, {"status": "approved"})
    event, _, payload, target_ref = second
    receipt_from_other_event = first[1]

    result = stack["boundary"].execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload,
        target_ref=target_ref,
        approval_receipt=receipt_from_other_event,
    )

    assert result.executed is False
    assert result.reason == "approval_claim_mismatch"
    assert _read_resource(stack["target"])[1] == 1


def test_payload_change_after_approval_fails_before_any_effect(stack):
    event, receipt, _, target_ref = _request(stack, {"status": "approved"})

    result = stack["boundary"].execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        {"value": {"status": "changed"}},
        target_ref=target_ref,
        approval_receipt=receipt,
    )

    assert result.executed is False
    assert result.reason == "payload_mismatch"
    assert _read_resource(stack["target"])[1] == 1
    assert stack["handler_calls"] == []


def test_generation_high_water_mark_rejects_aba_even_when_version_and_hash_match(stack):
    request = _request(stack, {"status": "approved"})
    target = stack["target"]
    row = _read_resource(target)
    connection = sqlite3.connect(target.database_path)
    try:
        connection.execute("DELETE FROM aion_resources WHERE resource_id = ?", ("resource-1",))
        with pytest.raises(sqlite3.IntegrityError, match="generation_must_increase"):
            connection.execute(
                "INSERT INTO aion_resources "
                "(resource_id, generation, version, value_json, content_hash) "
                "VALUES (?, 1, 1, ?, ?)",
                ("resource-1", row[2], row[3]),
            )
        connection.execute(
            "INSERT INTO aion_resources "
            "(resource_id, generation, version, value_json, content_hash) "
            "VALUES (?, 2, 1, ?, ?)",
            ("resource-1", row[2], row[3]),
        )
        connection.commit()
    finally:
        connection.close()

    result = _execute(stack, request)

    assert result.executed is False
    assert result.reason == "target_generation_mismatch"
    assert _read_resource(target)[0:2] == (2, 1)
    assert stack["handler_calls"] == []


def test_competing_updates_on_same_expected_version_allow_only_one(stack):
    requests = [
        _request(stack, {"status": "left"}),
        _request(stack, {"status": "right"}),
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda item: _execute(stack, item), requests))

    assert sum(result.executed for result in results) == 1
    assert _read_resource(stack["target"])[1] == 2
    assert stack["handler_calls"] == []


def test_concurrent_replay_is_idempotent_and_updates_only_once(stack):
    request = _request(stack, {"status": "approved"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _execute(stack, request), range(2)))

    assert all(result.executed for result in results)
    assert results[0].payload == results[1].payload
    assert _read_resource(stack["target"])[1] == 2
    assert stack["handler_calls"] == []


def test_sql_looking_payload_is_stored_as_data(stack):
    dangerous_looking_value = "x'); DROP TABLE aion_resources; --"
    result = _execute(stack, _request(stack, dangerous_looking_value))

    assert result.executed is True
    assert _read_resource(stack["target"])[1] == 2
    assert json.loads(_read_resource(stack["target"])[2]) == dangerous_looking_value


def test_sqlite_target_without_real_or_test_approval_remains_closed(stack):
    event, receipt, payload, target_ref = _request(stack, {"status": "approved"})
    boundary = ExecutionBoundary(
        stack["channel"],
        stack["boundary"].registry,
        target_authority=stack["target"],
    )

    result = boundary.execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload,
        target_ref=target_ref,
        approval_receipt=receipt,
    )

    assert result.executed is False
    assert result.reason == "external_approval_unavailable"
    assert _read_resource(stack["target"])[1] == 1
    assert stack["handler_calls"] == []


def test_approval_and_target_providers_cannot_share_the_same_database(tmp_path, monkeypatch):
    monkeypatch.setenv("AION_ENV", "test")
    target = SqliteTargetProvider(tmp_path / "shared.sqlite")
    _seed_resource(target)
    approvals = LocalTestApprovalProvider(tmp_path / "shared.sqlite")
    channel = ConfirmationChannel()
    registry = ToolRegistry()
    registry.register("sqlite_target", lambda payload: None)
    ref = target.ref("resource-1")
    snapshot = target.snapshot(SqliteTargetProvider.ACTION, ref)
    payload = {"value": {"status": "new"}}
    event = channel.issue(
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload=payload,
        target_ref=ref.identity,
        target_version=snapshot.version,
        target_hash=snapshot.content_hash,
        expected_generation=snapshot.generation,
    )
    receipt = approvals.issue_test_approval(event, payload)
    result = ExecutionBoundary(
        channel, registry, target, approvals
    ).execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload,
        target_ref=ref,
        approval_receipt=receipt,
    )

    assert result.executed is False
    assert result.reason == "external_approval_unavailable"
    assert _read_resource(target)[1] == 1


def test_local_approval_provider_is_not_constructible_outside_test_mode(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("AION_ENV", raising=False)
    with pytest.raises(RuntimeError, match="AION_ENV=test"):
        LocalTestApprovalProvider(tmp_path / "jti.sqlite")
    with pytest.raises(RuntimeError, match="AION_ENV=test"):
        SqliteTargetProvider(tmp_path / "target.sqlite")


def test_duplicate_request_id_with_changed_payload_is_rejected(stack):
    request = _request(stack, {"status": "approved"})
    assert _execute(stack, request).executed is True
    event, receipt, _, target_ref = request

    result = stack["boundary"].execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        {"value": {"status": "different"}},
        target_ref=target_ref,
        approval_receipt=receipt,
    )

    assert result.executed is False
    assert result.reason == "approval_claim_mismatch"
    assert _read_resource(stack["target"])[1] == 2


def test_gateway_binds_stable_database_resource_id_and_generation(stack):
    from aion.agency.gateway import AgencyGateway

    gateway = AgencyGateway(
        stack["channel"],
        lambda request: (True, "allowed"),
        target_authority=stack["target"],
    )
    payload = {"value": {"status": "from-gateway"}}
    ref = stack["target_ref"]
    decision = gateway.route({
        "action": SqliteTargetProvider.ACTION,
        "tool": SqliteTargetProvider.TOOL,
        "session_id": "session-1",
        "payload": payload,
        "target_ref": ref,
    })

    assert decision.confirmation is not None
    event = decision.confirmation
    assert event.target_ref == ref.identity
    assert event.expected_generation == 1
    assert event.target_version == "1"
    receipt = stack["approvals"].issue_test_approval(event, payload)
    result = stack["boundary"].execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload,
        target_ref=ref,
        approval_receipt=receipt,
    )
    assert result.executed is True
    assert _read_resource(stack["target"])[1] == 2


def test_local_approval_provider_validates_test_mode_ttl_payload_and_one_receipt(
    stack,
):
    with pytest.raises(ValueError, match="ttl_seconds"):
        LocalTestApprovalProvider(ttl_seconds=0)
    memory_provider = LocalTestApprovalProvider()
    assert memory_provider.store_identity == ":memory:"
    memory_provider.close()

    event, receipt, payload, _ = _request(stack, {"status": "approved"})
    with pytest.raises(ApprovalError, match="approval_already_issued"):
        stack["approvals"].issue_test_approval(event, payload)
    with pytest.raises(ApprovalError, match="payload_mismatch"):
        stack["approvals"].issue_test_approval(
            event, {"value": {"status": "different"}}
        )
    assert receipt.jti


def test_local_approval_provider_rejects_expired_or_incomplete_events(stack):
    event, _, payload, _ = _request(stack, {"status": "approved"})
    expired = replace(
        event, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    with pytest.raises(ApprovalError, match="expired"):
        stack["approvals"].issue_test_approval(expired, payload)
    with pytest.raises(ApprovalError, match="unissued_confirmation"):
        stack["approvals"].issue_test_approval(None, payload)

    incomplete = stack["channel"].issue(
        "update_resource", "sqlite_target", "session-1", payload=payload,
        target_ref="sqlite:test:resource", target_version="1", target_hash="hash",
    )
    with pytest.raises(ApprovalError, match="expected_generation_missing"):
        stack["approvals"].issue_test_approval(incomplete, payload)
    invalid_version = stack["channel"].issue(
        "update_resource", "sqlite_target", "session-1", payload=payload,
        target_ref="sqlite:test:resource", target_version="v1", target_hash="hash",
        expected_generation=1,
    )
    with pytest.raises(ApprovalError, match="expected_version_invalid"):
        stack["approvals"].issue_test_approval(invalid_version, payload)


def test_local_approval_provider_rejects_subsecond_expiry_and_unknown_jti(
    stack, monkeypatch
):
    event, receipt, payload, _ = _request(stack, {"status": "approved"})
    soon = replace(
        event,
        expires_at=datetime.fromtimestamp(1000.5, timezone.utc),
    )
    monkeypatch.setattr(
        "aion.execution.local_test_approval.time.time", lambda: 1000.1
    )
    with pytest.raises(ApprovalError, match="expired"):
        stack["approvals"].issue_test_approval(soon, payload)
    unknown = replace(receipt, jti="not-in-approval-store")
    with pytest.raises(ApprovalError, match="approval_jti_unknown"):
        stack["approvals"].is_jti_unused(unknown)


def test_local_approval_provider_rejects_malformed_and_expired_signed_receipts(stack):
    event, receipt, payload, _ = _request(stack, {"status": "approved"})
    malformed = replace(receipt, signature=object())
    with pytest.raises(ApprovalError, match="approval_signature_invalid"):
        stack["approvals"].validate_signature(malformed, event, payload)

    now = int(datetime.now(timezone.utc).timestamp())
    expired = replace(
        receipt,
        issued_at=now - 20,
        expires_at=now - 10,
        signature="",
    )
    expired = replace(
        expired,
        signature=stack["approvals"]._sign(expired.signed_claims()),
    )
    with pytest.raises(ApprovalError, match="approval_expired"):
        stack["approvals"].validate_signature(expired, event, payload)
    stack["approvals"].validate_signature(
        expired, event, payload, allow_expired=True
    )


def test_consumed_jti_is_reported_as_replayed(stack):
    event, receipt, _, _ = _request(stack, {"status": "approved"})
    assert _execute(stack, (event, receipt, {"value": {"status": "approved"}}, stack["target_ref"])).executed

    with pytest.raises(ApprovalError, match="approval_replayed"):
        stack["approvals"].is_jti_unused(receipt)
    with pytest.raises(ApprovalError, match="approval_replayed"):
        stack["approvals"].consume(
            receipt, event, {"value": {"status": "approved"}}
        )


def test_target_provider_rejects_unsupported_shapes_and_foreign_refs(stack):
    request = _request(stack, {"status": "approved"})
    event, receipt, payload, ref = request
    target = stack["target"]
    approvals = stack["approvals"]

    assert target.identity(replace(ref, database_id="foreign-db")) is None
    with pytest.raises(ValueError, match="resource_id"):
        target.ref("  ")
    with pytest.raises(ValueError, match="atomic_target_execution_unavailable"):
        target.snapshot("delete_resource", ref)
    with pytest.raises(ValueError, match="file-backed"):
        SqliteTargetProvider(":memory:")
    assert SqliteTargetProvider._path_identity(":memory:") == ":memory:"

    wrong_ref_result = target.compare_and_update(
        approvals, event, receipt, payload, replace(ref, database_id="foreign-db")
    )
    wrong_shape_result = target.compare_and_update(
        approvals, event, receipt, {"value": "x", "sql": "DROP TABLE"}, ref
    )
    wrong_provider_result = target.compare_and_update(
        object(), event, receipt, payload, ref
    )
    assert wrong_ref_result.reason == "target_ref_mismatch"
    assert wrong_shape_result.reason == "atomic_target_execution_unavailable"
    assert wrong_provider_result.reason == "external_approval_unavailable"


def test_target_provider_rejects_missing_and_corrupt_rows(stack):
    event, receipt, payload, ref = _request(stack, {"status": "approved"})
    connection = sqlite3.connect(stack["target"].database_path)
    try:
        connection.execute(
            "DELETE FROM aion_resources WHERE resource_id = ?", (ref.resource_id,)
        )
        connection.commit()
    finally:
        connection.close()
    missing = stack["target"].compare_and_update(
        stack["approvals"], event, receipt, payload, ref
    )
    assert missing.reason == "target_not_found"
    with pytest.raises(FileNotFoundError, match="target_not_found"):
        stack["target"].snapshot(SqliteTargetProvider.ACTION, ref)

    _seed_resource(stack["target"], generation=2)
    event, receipt, payload, ref = _request(stack, {"status": "approved-again"})
    connection = sqlite3.connect(stack["target"].database_path)
    try:
        connection.execute(
            "UPDATE aion_resources SET content_hash = 'corrupt' WHERE resource_id = ?",
            (ref.resource_id,),
        )
        connection.commit()
    finally:
        connection.close()
    corrupt = stack["target"].compare_and_update(
        stack["approvals"], event, receipt, payload, ref
    )
    assert corrupt.reason == "target_integrity_error"
    with pytest.raises(ValueError, match="target_integrity_error"):
        stack["target"].snapshot(SqliteTargetProvider.ACTION, ref)


def test_target_provider_request_ledger_conflict_and_target_jti_replay(stack):
    request = _request(stack, {"status": "approved"})
    assert _execute(stack, request).executed
    event, _receipt, _, _ = request
    connection = sqlite3.connect(stack["target"].database_path)
    try:
        connection.execute(
            "UPDATE aion_executions SET request_hash = 'tampered' WHERE request_id = ?",
            (event.request_id,),
        )
        connection.commit()
    finally:
        connection.close()
    replay = _execute(stack, request)
    assert replay.reason == "request_id_conflict"

    fresh_event, fresh_receipt, fresh_payload, fresh_ref = _request(
        stack, {"status": "another"}
    )
    connection = sqlite3.connect(stack["target"].database_path)
    try:
        connection.execute(
            "INSERT INTO aion_used_jti(jti, request_id) VALUES (?, ?)",
            (fresh_receipt.jti, "someone-else"),
        )
        connection.commit()
    finally:
        connection.close()
    blocked = stack["target"].compare_and_update(
        stack["approvals"], fresh_event, fresh_receipt, fresh_payload, fresh_ref
    )
    assert blocked.reason == "approval_replayed"
    assert stack["handler_calls"] == []


def test_target_compare_and_update_rolls_back_on_zero_row_update(stack):
    event, receipt, payload, ref = _request(stack, {"status": "approved"})
    connection = sqlite3.connect(stack["target"].database_path)
    try:
        connection.execute(
            "CREATE TRIGGER force_zero_update BEFORE UPDATE ON aion_resources "
            "BEGIN SELECT RAISE(IGNORE); END"
        )
        connection.commit()
    finally:
        connection.close()

    result = _execute(stack, (event, receipt, payload, ref))

    assert result.executed is False
    assert result.reason == "atomic_target_execution_unavailable"
    row = _read_resource(stack["target"])
    assert row[1] == 1
    connection = sqlite3.connect(stack["target"].database_path)
    try:
        assert connection.execute("SELECT count(*) FROM aion_used_jti").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM aion_executions").fetchone()[0] == 0
    finally:
        connection.close()
    with pytest.raises(ApprovalError, match="approval_replayed"):
        stack["approvals"].is_jti_unused(receipt)


def test_target_provider_stays_disabled_if_environment_changes(stack, monkeypatch):
    event, receipt, payload, ref = _request(stack, {"status": "approved"})
    monkeypatch.setenv("AION_ENV", "production")
    result = stack["target"].compare_and_update(
        stack["approvals"], event, receipt, payload, ref
    )
    assert result.executed is False
    assert result.reason == "atomic_target_execution_unavailable"
    assert _read_resource(stack["target"])[1] == 1


def test_gateway_rejects_malformed_target_authority_responses(stack):
    from types import SimpleNamespace

    from aion.agency.gateway import AgencyGateway

    class FakeAuthority:
        def __init__(self, snapshot=None, error=None):
            self._snapshot = snapshot
            self._error = error

        def snapshot(self, action, target_ref):
            if self._error:
                raise self._error
            return self._snapshot

    ref = stack["target_ref"]
    payload = {"value": "x"}

    def route(authority, target=ref):
        return AgencyGateway(
            stack["channel"], lambda request: (True, "allowed"), authority
        ).route({
            "action": "update_resource",
            "tool": "sqlite_target",
            "session_id": "session-1",
            "payload": payload,
            "target_ref": target,
        })

    with pytest.raises(TypeError):
        AgencyGateway(stack["channel"], lambda request: (True, "allowed")).route([])
    invalid_ref = route(FakeAuthority(), target=object())
    assert invalid_ref.reason == "target_ref_invalid"
    missing = route(FakeAuthority(error=FileNotFoundError()))
    assert missing.reason == "target_not_found"
    failed = route(FakeAuthority(error=RuntimeError("offline")))
    assert failed.reason == "target_authority_error"
    no_identity = route(FakeAuthority(SimpleNamespace(target_ref=object())))
    assert no_identity.reason == "target_authority_invalid"
    mismatch = route(FakeAuthority(SimpleNamespace(
        target_ref=SimpleNamespace(path="different"), version="1", content_hash="hash"
    )))
    assert mismatch.reason == "target_ref_mismatch"
    invalid_generation = route(FakeAuthority(SimpleNamespace(
        target_ref=ref, version="1", content_hash="hash", generation=True
    )))
    assert invalid_generation.reason == "target_generation_invalid"
    no_state = route(FakeAuthority(SimpleNamespace(
        target_ref=ref, version=None, content_hash="hash"
    )))
    assert no_state.reason == "target_state_unavailable"



def test_hard_link_between_target_and_approval_store_is_detected(tmp_path, monkeypatch):
    monkeypatch.setenv("AION_ENV", "test")
    target = SqliteTargetProvider(tmp_path / "hardlink-target.sqlite")
    _seed_resource(target)
    hard_link = tmp_path / "approval-hardlink.sqlite"
    try:
        os.link(target.database_path, hard_link)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"hard links are unavailable on this platform/filesystem: {exc}")
    approvals = LocalTestApprovalProvider(hard_link)
    assert target.database_identity == approvals.store_identity

    channel = ConfirmationChannel()
    registry = ToolRegistry()
    registry.register("sqlite_target", lambda payload: None)
    ref = target.ref("resource-1")
    snapshot = target.snapshot(SqliteTargetProvider.ACTION, ref)
    payload = {"value": {"status": "approved"}}
    event = channel.issue(
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload=payload,
        target_ref=ref.identity,
        target_version=snapshot.version,
        target_hash=snapshot.content_hash,
        expected_generation=snapshot.generation,
    )
    receipt = approvals.issue_test_approval(event, payload)
    result = ExecutionBoundary(
        channel, registry, target_authority=target, approval_provider=approvals
    ).execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload,
        target_ref=ref,
        approval_receipt=receipt,
    )
    assert result.executed is False
    assert result.reason == "external_approval_unavailable"
    assert _read_resource(target)[1] == 1


def test_target_symlink_repoint_does_not_redirect_database_connections(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("AION_ENV", "test")
    real_database = tmp_path / "actual-target.sqlite"
    link = tmp_path / "target-link.sqlite"
    try:
        link.symlink_to(real_database)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks are unavailable on this platform/filesystem: {exc}")

    target = SqliteTargetProvider(link)
    assert target.database_path == os.path.realpath(real_database)
    _seed_resource(target, value={"status": "original"})
    original_identity = target.database_identity

    redirected_database = tmp_path / "redirected.sqlite"
    redirected = SqliteTargetProvider(redirected_database)
    _seed_resource(redirected, value={"status": "redirected"})
    link.unlink()
    try:
        link.symlink_to(redirected_database)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink repoint is unavailable on this platform/filesystem: {exc}")

    snapshot = target.snapshot(SqliteTargetProvider.ACTION, target.ref("resource-1"))
    assert target.database_identity == original_identity
    assert snapshot.target_ref.database_id == target.database_id
    assert json.loads(snapshot.value_json) == {"status": "original"}


def test_target_provider_rejects_replacement_of_canonical_database_file(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("AION_ENV", "test")
    target = SqliteTargetProvider(tmp_path / "pinned-target.sqlite")
    _seed_resource(target, value={"status": "original"})
    replacement_path = tmp_path / "replacement.sqlite"
    replacement = SqliteTargetProvider(replacement_path)
    _seed_resource(replacement, value={"status": "replacement"})
    os.replace(replacement.database_path, target.database_path)

    with pytest.raises(RuntimeError, match="target_database_identity_changed"):
        target.snapshot(SqliteTargetProvider.ACTION, target.ref("resource-1"))



def test_target_file_identity_and_generation_ledger_survive_reopen_and_removal(
    stack,
):
    target = stack["target"]
    ref = stack["target_ref"]
    assert SqliteTargetProvider._path_identity(target.database_path) == target.database_path
    assert target.identity(object()) is None
    assert target.identity(replace(ref, resource_id="")) is None

    reopened = SqliteTargetProvider(target.database_path)
    assert reopened.database_id == target.database_id
    assert reopened.database_identity == target.database_identity
    assert reopened.ref("resource-1").identity == ref.identity
    assert _read_resource(reopened)[0] == 1
    with pytest.raises(FileNotFoundError, match="target_not_found"):
        reopened.snapshot(SqliteTargetProvider.ACTION, reopened.ref("missing"))

    os.unlink(target.database_path)
    with pytest.raises(RuntimeError, match="target_database_identity_changed"):
        target.snapshot(SqliteTargetProvider.ACTION, ref)


@pytest.mark.parametrize("change", ["missing", "replaced"])
def test_target_provider_rechecks_file_identity_after_connect(
    stack, monkeypatch, change
):
    target = stack["target"]
    ref = stack["target_ref"]
    original_identity = target.database_identity
    calls = 0

    def simulate_path_change(path):
        nonlocal calls
        calls += 1
        if change == "missing":
            raise OSError("simulated path disappearance")
        return original_identity[0], original_identity[1] + 1

    monkeypatch.setattr(target, "_file_identity", simulate_path_change)
    with pytest.raises(RuntimeError, match="target_database_identity_changed"):
        target.snapshot(SqliteTargetProvider.ACTION, ref)
    assert calls == 1


@pytest.mark.parametrize("race_connection", [1, 2])
def test_descriptor_binding_rejects_swap_during_sqlite_connect(
    stack, tmp_path, monkeypatch, race_connection
):
    target = stack["target"]
    replacement = SqliteTargetProvider(tmp_path / "race-replacement.sqlite")
    _seed_resource(replacement, value={"status": "replacement"})
    request = _request(stack, {"status": "approved"})
    target_path = target.database_path
    replacement_path = replacement.database_path
    parked_path = str(tmp_path / "race-parked.sqlite")
    real_connect = sqlite3.connect
    connect_calls = 0
    opened_paths = []

    def swap_file_during_connect(database, *args, **kwargs):
        nonlocal connect_calls
        database_string = os.fspath(database)
        if database_string.startswith("file:/proc/self/fd/"):
            connect_calls += 1
            if connect_calls == race_connection:
                os.replace(target_path, parked_path)
                os.replace(replacement_path, target_path)
                try:
                    connection = real_connect(database, *args, **kwargs)
                    opened_paths.append(
                        connection.execute("PRAGMA database_list").fetchone()[2]
                    )
                finally:
                    os.replace(target_path, replacement_path)
                    os.replace(parked_path, target_path)
                return connection
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(
        "aion.target.sqlite_authority.sqlite3.connect", swap_file_during_connect
    )
    result = _execute(stack, request)

    assert result.executed is False
    assert result.reason == "atomic_target_execution_unavailable"
    assert connect_calls >= race_connection
    assert len(opened_paths) == 1
    assert os.path.realpath(opened_paths[0]) == os.path.realpath(parked_path)
    assert _read_resource(target)[1] == 1
    assert json.loads(_read_resource(replacement)[2]) == {"status": "replacement"}
    assert stack["handler_calls"] == []



def test_copied_database_rejects_original_receipt_without_effect(stack, tmp_path):
    target = stack["target"]
    event, receipt, payload, original_ref = _request(
        stack, {"status": "approved-on-original"}
    )
    original_snapshot = target.snapshot(SqliteTargetProvider.ACTION, original_ref)
    original_row = _read_resource(target)

    clone_path = tmp_path / "cloned-target.sqlite"
    shutil.copy2(target.database_path, clone_path)
    clone = SqliteTargetProvider(clone_path)
    clone_ref = clone.ref("resource-1")
    clone_snapshot = clone.snapshot(SqliteTargetProvider.ACTION, clone_ref)

    assert clone.database_id == target.database_id
    assert clone.database_identity[0] == target.database_identity[0]
    assert clone.database_identity[1] != target.database_identity[1]
    assert (clone_snapshot.generation, clone_snapshot.version, clone_snapshot.content_hash) == (
        original_snapshot.generation,
        original_snapshot.version,
        original_snapshot.content_hash,
    )
    assert clone_ref.identity != original_ref.identity
    assert event.target_ref == original_ref.identity

    clone_boundary = ExecutionBoundary(
        stack["channel"],
        stack["boundary"].registry,
        target_authority=clone,
        approval_provider=stack["approvals"],
    )
    result = clone_boundary.execute(
        event,
        SqliteTargetProvider.ACTION,
        SqliteTargetProvider.TOOL,
        "session-1",
        payload,
        target_ref=clone_ref,
        approval_receipt=receipt,
    )

    assert result.executed is False
    assert result.reason == "target_ref_mismatch"
    assert _read_resource(target) == original_row
    assert _read_resource(clone) == original_row
    assert stack["approvals"].is_jti_unused(receipt) is True
    for provider in (target, clone):
        with sqlite3.connect(provider.database_path) as connection:
            assert connection.execute(
                "SELECT count(*) FROM aion_executions"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM aion_used_jti"
            ).fetchone()[0] == 0

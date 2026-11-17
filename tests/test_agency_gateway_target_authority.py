from __future__ import annotations

from aion.agency.gateway import AgencyGateway
from aion.execution.channel import ConfirmationChannel
from aion.target.filesystem_authority import FileSystemTargetAuthority, TargetRef


def test_gateway_binds_authoritative_filesystem_snapshot(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"authoritative content")
    authority = FileSystemTargetAuthority()
    target_ref = TargetRef(str(path))
    snapshot = authority.snapshot("read_file", target_ref)
    gateway = AgencyGateway(
        ConfirmationChannel(), lambda request: (True, "allowed"),
        target_authority=authority,
    )

    decision = gateway.route({
        "action": "read_file", "tool": "filesystem-tool", "session_id": "session-1",
        "payload": {"path": str(path)}, "target_ref": target_ref,
        "target_version": "caller-version", "target_hash": "caller-hash",
    })

    assert decision.confirmation is not None
    assert decision.confirmation.target_ref == target_ref.path
    assert decision.confirmation.target_version == snapshot.version
    assert decision.confirmation.target_hash == snapshot.content_hash


def test_gateway_ignores_fake_caller_target_hash_when_authority_exists(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"real resource")
    authority = FileSystemTargetAuthority()
    target_ref = TargetRef(str(path))
    snapshot = authority.snapshot("update_file", target_ref)
    gateway = AgencyGateway(
        ConfirmationChannel(), lambda request: (True, "allowed"),
        target_authority=authority,
    )

    decision = gateway.route({
        "action": "update_file", "tool": "filesystem-tool", "session_id": "session-1",
        "payload": {"path": str(path)}, "target_ref": target_ref,
        "target_version": "forged-version", "target_hash": "forged-hash",
    })
    assert decision.confirmation is not None
    assert decision.confirmation.target_ref == target_ref.path
    assert decision.confirmation.target_version == snapshot.version
    assert decision.confirmation.target_hash == snapshot.content_hash
    assert decision.confirmation.target_hash != "forged-hash"


def test_gateway_rejects_target_claim_without_authority_or_reference():
    gateway = AgencyGateway(
        ConfirmationChannel(), lambda request: (True, "allowed")
    )
    decision = gateway.route({
        "action": "update_file", "tool": "filesystem-tool", "session_id": "session-1",
        "payload": {"path": "resource.txt"}, "target_version": "v1",
        "target_hash": "hash-v1",
    })
    assert decision.confirmation is None
    assert decision.requires_confirmation is False
    assert decision.reason == "target_ref_required"


def test_gateway_rejects_reference_without_authority(tmp_path):
    target_ref = TargetRef(str(tmp_path / "resource.txt"))
    gateway = AgencyGateway(
        ConfirmationChannel(), lambda request: (True, "allowed")
    )
    decision = gateway.route({
        "action": "update_file", "tool": "filesystem-tool", "session_id": "session-1",
        "payload": {"path": target_ref.path}, "target_ref": target_ref,
    })
    assert decision.confirmation is None
    assert decision.reason == "target_authority_required"

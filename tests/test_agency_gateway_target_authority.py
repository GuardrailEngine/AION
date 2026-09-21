from __future__ import annotations

from aion.agency.gateway import AgencyGateway
from aion.execution.channel import ConfirmationChannel
from aion.target.filesystem_authority import (
    FileSystemTargetAuthority,
    TargetRef,
)


def test_gateway_uses_authoritative_filesystem_snapshot(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"authoritative content")

    authority = FileSystemTargetAuthority()
    target_ref = TargetRef(str(path))
    snapshot = authority.snapshot("read_file", target_ref)

    gateway = AgencyGateway(
        ConfirmationChannel(),
        lambda request: (True, "allowed"),
        target_authority=authority,
    )

    decision = gateway.route(
        {
            "action": "read_file",
            "tool": "filesystem-tool",
            "session_id": "session-1",
            "payload": {"path": str(path)},
            "target_ref": target_ref,
            "target_version": "caller-version",
            "target_hash": "caller-hash",
        }
    )

    assert decision.confirmation is not None
    assert decision.confirmation.target_version == snapshot.version
    assert decision.confirmation.target_hash == snapshot.content_hash


def test_gateway_ignores_fake_caller_target_hash_when_authority_exists(tmp_path):
    path = tmp_path / "resource.txt"
    path.write_bytes(b"real resource")

    authority = FileSystemTargetAuthority()
    target_ref = TargetRef(str(path))
    snapshot = authority.snapshot("update_file", target_ref)

    gateway = AgencyGateway(
        ConfirmationChannel(),
        lambda request: (True, "allowed"),
        target_authority=authority,
    )

    decision = gateway.route(
        {
            "action": "update_file",
            "tool": "filesystem-tool",
            "session_id": "session-1",
            "payload": {"path": str(path)},
            "target_ref": target_ref,
            "target_version": "forged-version",
            "target_hash": "forged-hash",
        }
    )

    assert decision.confirmation is not None
    assert decision.confirmation.target_version == snapshot.version
    assert decision.confirmation.target_hash == snapshot.content_hash
    assert decision.confirmation.target_hash != "forged-hash"


def test_gateway_without_authority_preserves_caller_values():
    gateway = AgencyGateway(
        ConfirmationChannel(),
        lambda request: (True, "allowed"),
    )

    decision = gateway.route(
        {
            "action": "legacy_action",
            "tool": "legacy-tool",
            "session_id": "session-1",
            "payload": {"value": 1},
            "target_version": "legacy-version",
            "target_hash": "legacy-hash",
        }
    )

    assert decision.confirmation is not None
    assert decision.confirmation.target_version == "legacy-version"
    assert decision.confirmation.target_hash == "legacy-hash"

from aion.execution.channel import ConfirmationChannel


def test_audit_chain_with_multiple_records_is_valid():
    channel = ConfirmationChannel()

    event = channel.issue(
        action="read",
        tool="filesystem",
        session_id="session-1",
    )
    channel.verify(
        event=event,
        action="read",
        tool="filesystem",
        session_id="session-1",
    )

    assert channel.verify_audit_integrity() == (True, None)


def test_direct_internal_audit_tampering_is_detected_at_correct_index():
    channel = ConfirmationChannel()

    event = channel.issue(
        action="read",
        tool="filesystem",
        session_id="session-1",
    )
    channel.verify(
        event=event,
        action="read",
        tool="filesystem",
        session_id="session-1",
    )

    channel._audit[1]["reason"] = "tampered"

    assert channel.verify_audit_integrity() == (False, 1)


def test_single_audit_record_validates_from_genesis():
    channel = ConfirmationChannel()

    channel.issue(
        action="read",
        tool="filesystem",
        session_id="session-1",
    )

    records = channel.audit_log()

    assert len(records) == 1
    assert records[0]["prev_hash"] == "0" * 64
    assert channel.verify_audit_integrity() == (True, None)


def test_empty_audit_log_is_integrity_valid():
    channel = ConfirmationChannel()

    assert channel.verify_audit_integrity() == (True, None)


def test_mutating_audit_log_copy_does_not_mutate_internal_chain():
    channel = ConfirmationChannel()

    channel.issue(
        action="read",
        tool="filesystem",
        session_id="session-1",
    )

    records = channel.audit_log()
    records[0]["event"] = "tampered"

    assert channel.verify_audit_integrity() == (True, None)
    assert channel.audit_log()[0]["event"] == "issued"

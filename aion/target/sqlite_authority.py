"""A single-operation, test-only SQLite compare-and-update target provider."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from aion.execution.channel import ConfirmationEvent, hash_payload
from aion.execution.local_test_approval import (
    ApprovalError,
    ApprovalReceipt,
    LocalTestApprovalProvider,
)


@dataclass(frozen=True)
class SqliteTargetRef:
    """Stable database/resource identity; it contains no file-system path."""

    database_id: str
    resource_id: str
    file_device: int
    file_inode: int

    @property
    def identity(self) -> str:
        return (
            f"sqlite:{self.database_id}:{self.file_device}:"
            f"{self.file_inode}:{self.resource_id}"
        )


@dataclass(frozen=True)
class SqliteTargetSnapshot:
    target_ref: SqliteTargetRef
    version: str
    content_hash: str
    generation: int
    value_json: str


@dataclass(frozen=True)
class TargetExecutionResult:
    executed: bool
    reason: str
    payload: dict[str, Any] | None = None
    replayed: bool = False


class SqliteTargetProvider:
    """Support only update_resource on one row in a dedicated SQLite database.

    The provider is gated by ``AION_ENV=test``. It performs no filesystem,
    network, subprocess, or registered-tool side effects. The database stores a
    persistent generation high-water mark so delete/recreate cannot reuse an
    earlier generation.
    """

    ACTION = "update_resource"
    TOOL = "sqlite_target"

    def __init__(self, database_path: str | os.PathLike[str]) -> None:
        self._require_test_environment()
        raw_path = os.fspath(database_path)
        if raw_path == ":memory:":
            raise ValueError("SqliteTargetProvider requires a dedicated file-backed database")
        if not os.path.isdir("/proc/self/fd"):
            raise RuntimeError("safe SQLite descriptor binding requires /proc/self/fd")
        requested_path = Path(raw_path).expanduser()
        requested_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = str(requested_path.resolve(strict=False))
        descriptor = self._open_database_file(self.database_path, create=True)
        try:
            file_stat = os.fstat(descriptor)
            self.database_identity = file_stat.st_dev, file_stat.st_ino
        finally:
            os.close(descriptor)
        self.database_id = ""
        self._initialize()

    @staticmethod
    def _require_test_environment() -> None:
        if os.environ.get("AION_ENV") != "test":
            raise RuntimeError(
                "SqliteTargetProvider is available only when AION_ENV=test"
            )

    @staticmethod
    def _path_identity(path: str) -> str:
        if path == ":memory:":
            return path
        return str(Path(path).expanduser().resolve())

    @staticmethod
    def _file_identity(path: str) -> tuple[int, int]:
        file_stat = os.stat(path)
        return file_stat.st_dev, file_stat.st_ino

    @staticmethod
    def _open_database_file(path: str, *, create: bool = False) -> int:
        flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        if create:
            try:
                return os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o666)
            except FileExistsError:
                pass
        return os.open(path, flags)

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @classmethod
    def _hash_json_text(cls, value_json: str) -> str:
        return hashlib.sha256(value_json.encode("utf-8")).hexdigest()

    def _connect(self) -> sqlite3.Connection:
        self._require_test_environment()
        try:
            descriptor = self._open_database_file(self.database_path)
        except OSError as exc:
            raise RuntimeError("target_database_identity_changed") from exc
        connection = None
        try:
            file_stat = os.fstat(descriptor)
            if (file_stat.st_dev, file_stat.st_ino) != self.database_identity:
                raise RuntimeError("target_database_identity_changed")
            connection = sqlite3.connect(
                f"file:/proc/self/fd/{descriptor}?mode=rw",
                timeout=10,
                isolation_level=None,
                uri=True,
            )
            try:
                current_identity = self._file_identity(self.database_path)
            except OSError as exc:
                raise RuntimeError("target_database_identity_changed") from exc
            if current_identity != self.database_identity:
                raise RuntimeError("target_database_identity_changed")
            main_path = next(
                (
                    row[2]
                    for row in connection.execute("PRAGMA database_list")
                    if row[1] == "main"
                ),
                None,
            )
            if main_path is None or os.path.realpath(main_path) != self.database_path:
                raise RuntimeError("target_database_identity_changed")
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 10000")
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except Exception:
            if connection is not None:
                connection.close()
            raise
        finally:
            os.close(descriptor)

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """CREATE TABLE IF NOT EXISTS aion_meta (
                       key TEXT PRIMARY KEY,
                       value TEXT NOT NULL
                   );
                   CREATE TABLE IF NOT EXISTS aion_resources (
                       resource_id TEXT PRIMARY KEY CHECK (length(resource_id) > 0),
                       generation INTEGER NOT NULL CHECK (generation > 0),
                       version INTEGER NOT NULL CHECK (version > 0),
                       value_json TEXT NOT NULL,
                       content_hash TEXT NOT NULL
                   );
                   CREATE TABLE IF NOT EXISTS aion_resource_generations (
                       resource_id TEXT PRIMARY KEY,
                       last_generation INTEGER NOT NULL CHECK (last_generation > 0)
                   );
                   CREATE TABLE IF NOT EXISTS aion_used_jti (
                       jti TEXT PRIMARY KEY,
                       request_id TEXT NOT NULL UNIQUE
                   );
                   CREATE TABLE IF NOT EXISTS aion_executions (
                       request_id TEXT PRIMARY KEY,
                       request_hash TEXT NOT NULL,
                       jti TEXT NOT NULL UNIQUE,
                       result_json TEXT NOT NULL
                   );
                   CREATE TRIGGER IF NOT EXISTS aion_generation_must_increase
                   BEFORE INSERT ON aion_resources
                   WHEN EXISTS (
                       SELECT 1 FROM aion_resource_generations
                       WHERE resource_id = NEW.resource_id
                         AND NEW.generation <= last_generation
                   )
                   BEGIN
                       SELECT RAISE(ABORT, 'generation_must_increase');
                   END;
                   CREATE TRIGGER IF NOT EXISTS aion_generation_record_insert
                   AFTER INSERT ON aion_resources
                   BEGIN
                       INSERT INTO aion_resource_generations(resource_id, last_generation)
                       VALUES (NEW.resource_id, NEW.generation)
                       ON CONFLICT(resource_id) DO UPDATE
                       SET last_generation = excluded.last_generation;
                   END;
                   CREATE TRIGGER IF NOT EXISTS aion_generation_immutable
                   BEFORE UPDATE OF generation ON aion_resources
                   WHEN NEW.generation != OLD.generation
                   BEGIN
                       SELECT RAISE(ABORT, 'generation_is_immutable');
                   END;
                   CREATE TRIGGER IF NOT EXISTS aion_version_monotonic
                   BEFORE UPDATE OF version ON aion_resources
                   WHEN NEW.version != OLD.version + 1
                   BEGIN
                       SELECT RAISE(ABORT, 'version_must_increment_by_one');
                   END;"""
            )
            connection.execute("BEGIN IMMEDIATE")
            for resource in connection.execute(
                "SELECT resource_id, generation FROM aion_resources"
            ).fetchall():
                connection.execute(
                    "INSERT INTO aion_resource_generations "
                    "(resource_id, last_generation) VALUES (?, ?) "
                    "ON CONFLICT(resource_id) DO UPDATE SET last_generation = "
                    "MAX(last_generation, excluded.last_generation)",
                    (resource["resource_id"], resource["generation"]),
                )
            row = connection.execute(
                "SELECT value FROM aion_meta WHERE key = 'database_id'"
            ).fetchone()
            if row is None:
                self.database_id = str(uuid4())
                connection.execute(
                    "INSERT INTO aion_meta(key, value) VALUES ('database_id', ?)",
                    (self.database_id,),
                )
            else:
                self.database_id = str(row[0])
            connection.execute("COMMIT")
        except sqlite3.Error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def ref(self, resource_id: str) -> SqliteTargetRef:
        self._require_test_environment()
        if not isinstance(resource_id, str) or not resource_id.strip():
            raise ValueError("resource_id must be a non-empty string")
        return SqliteTargetRef(
            self.database_id,
            resource_id,
            self.database_identity[0],
            self.database_identity[1],
        )

    def identity(self, target_ref: SqliteTargetRef) -> str | None:
        if not isinstance(target_ref, SqliteTargetRef):
            return None
        if target_ref.database_id != self.database_id:
            return None
        if (
            not isinstance(target_ref.file_device, int)
            or isinstance(target_ref.file_device, bool)
            or not isinstance(target_ref.file_inode, int)
            or isinstance(target_ref.file_inode, bool)
            or (target_ref.file_device, target_ref.file_inode)
            != self.database_identity
        ):
            return None
        if not target_ref.resource_id.strip():
            return None
        return target_ref.identity

    def snapshot(
        self, action: str, target_ref: SqliteTargetRef
    ) -> SqliteTargetSnapshot:
        self._require_test_environment()
        if action != self.ACTION or self.identity(target_ref) is None:
            raise ValueError("atomic_target_execution_unavailable")
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT generation, version, value_json, content_hash "
                "FROM aion_resources WHERE resource_id = ?",
                (target_ref.resource_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError("target_not_found")
            calculated_hash = self._hash_json_text(row["value_json"])
            if calculated_hash != row["content_hash"]:
                raise ValueError("target_integrity_error")
            return SqliteTargetSnapshot(
                target_ref=target_ref,
                version=str(row["version"]),
                content_hash=row["content_hash"],
                generation=int(row["generation"]),
                value_json=row["value_json"],
            )
        finally:
            connection.close()

    @staticmethod
    def _request_hash(
        event: ConfirmationEvent,
        receipt: ApprovalReceipt,
        payload_hash: str,
    ) -> str:
        claims = {
            "aion.confirmation_event_id": event.request_id,
            "action": event.action,
            "expected_generation": event.expected_generation,
            "expected_version": event.target_version,
            "jti": receipt.jti,
            "payload_hash": payload_hash,
            "request_id": event.request_id,
            "session_id": event.session_id,
            "target_hash": event.target_hash,
            "target_ref": event.target_ref,
            "tool": event.tool,
        }
        return hashlib.sha256(
            SqliteTargetProvider._canonical_json(claims).encode("utf-8")
        ).hexdigest()

    def compare_and_update(
        self,
        approval_provider: LocalTestApprovalProvider,
        event: ConfirmationEvent,
        receipt: ApprovalReceipt,
        payload: Any,
        target_ref: SqliteTargetRef,
        *,
        event_was_consumed: bool = False,
    ) -> TargetExecutionResult:
        """Verify approval and atomically update one resource row or no row."""
        try:
            self._require_test_environment()
        except RuntimeError:
            return TargetExecutionResult(False, "atomic_target_execution_unavailable")
        if type(approval_provider) is not LocalTestApprovalProvider:
            return TargetExecutionResult(False, "external_approval_unavailable")
        if self.identity(target_ref) is None:
            return TargetExecutionResult(False, "target_ref_mismatch")
        if type(payload) is not dict or set(payload) != {"value"}:
            return TargetExecutionResult(False, "atomic_target_execution_unavailable")
        if (
            event.action != self.ACTION
            or event.tool != self.TOOL
            or event.target_ref != target_ref.identity
            or event.expected_generation is None
            or event.target_version is None
            or event.target_hash is None
        ):
            return TargetExecutionResult(False, "atomic_target_execution_unavailable")
        try:
            value_json = self._canonical_json(payload["value"])
            new_hash = self._hash_json_text(value_json)
            payload_hash = hash_payload(payload)
            request_hash = self._request_hash(event, receipt, payload_hash)
        except (TypeError, ValueError):
            return TargetExecutionResult(False, "payload_invalid")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT request_hash, jti, result_json FROM aion_executions "
                "WHERE request_id = ?",
                (event.request_id,),
            ).fetchone()
            if previous is not None:
                try:
                    approval_provider.validate_signature(
                        receipt, event, payload, allow_expired=True
                    )
                except ApprovalError as exc:
                    connection.execute("ROLLBACK")
                    return TargetExecutionResult(False, exc.reason)
                if (
                    previous["request_hash"] != request_hash
                    or previous["jti"] != receipt.jti
                ):
                    connection.execute("ROLLBACK")
                    return TargetExecutionResult(False, "request_id_conflict")
                connection.execute("COMMIT")
                return TargetExecutionResult(
                    True,
                    "ok",
                    json.loads(previous["result_json"]),
                    replayed=True,
                )

            if event_was_consumed:
                connection.execute("ROLLBACK")
                return TargetExecutionResult(False, "already_used")
            try:
                approval_provider.validate_signature(receipt, event, payload)
                approval_provider.is_jti_unused(receipt)
            except ApprovalError as exc:
                connection.execute("ROLLBACK")
                return TargetExecutionResult(False, exc.reason)

            used = connection.execute(
                "SELECT request_id FROM aion_used_jti WHERE jti = ?",
                (receipt.jti,),
            ).fetchone()
            if used is not None:
                connection.execute("ROLLBACK")
                return TargetExecutionResult(False, "approval_replayed")

            row = connection.execute(
                "SELECT generation, version, value_json, content_hash "
                "FROM aion_resources WHERE resource_id = ?",
                (target_ref.resource_id,),
            ).fetchone()
            if row is None:
                connection.execute("ROLLBACK")
                return TargetExecutionResult(False, "target_not_found")
            calculated_hash = self._hash_json_text(row["value_json"])
            if calculated_hash != row["content_hash"]:
                connection.execute("ROLLBACK")
                return TargetExecutionResult(False, "target_integrity_error")
            try:
                expected_version = int(event.target_version)
            except (TypeError, ValueError):
                connection.execute("ROLLBACK")
                return TargetExecutionResult(False, "target_binding_incomplete")
            if (
                int(row["generation"]) != event.expected_generation
                or int(row["version"]) != expected_version
                or row["content_hash"] != event.target_hash
            ):
                connection.execute("ROLLBACK")
                return TargetExecutionResult(False, "target_drift")

            # This separate ledger is consumed before mutation; if any later
            # target-DB step fails, the receipt remains spent and needs renewal.
            try:
                approval_provider.consume(receipt, event, payload)
            except ApprovalError as exc:
                connection.execute("ROLLBACK")
                return TargetExecutionResult(False, exc.reason)

            connection.execute(
                "INSERT INTO aion_used_jti(jti, request_id) VALUES (?, ?)",
                (receipt.jti, event.request_id),
            )
            updated = connection.execute(
                "UPDATE aion_resources "
                "SET value_json = ?, content_hash = ?, version = version + 1 "
                "WHERE resource_id = ? AND version = ? AND content_hash = ? "
                "AND generation = ? AND value_json = ?",
                (
                    value_json,
                    new_hash,
                    target_ref.resource_id,
                    expected_version,
                    event.target_hash,
                    event.expected_generation,
                    row["value_json"],
                ),
            ).rowcount
            if updated != 1:
                connection.execute("ROLLBACK")
                return TargetExecutionResult(
                    False, "atomic_target_execution_unavailable"
                )
            result_payload: dict[str, Any] = {
                "request_id": event.request_id,
                "resource_id": target_ref.resource_id,
                "database_id": self.database_id,
                "generation": event.expected_generation,
                "version": expected_version + 1,
                "content_hash": new_hash,
            }
            connection.execute(
                "INSERT INTO aion_executions(request_id, request_hash, jti, result_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    event.request_id,
                    request_hash,
                    receipt.jti,
                    self._canonical_json(result_payload),
                ),
            )
            connection.execute("COMMIT")
            return TargetExecutionResult(True, "ok", result_payload)
        except (sqlite3.Error, ApprovalError) as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            reason = (
                exc.reason
                if isinstance(exc, ApprovalError)
                else "atomic_target_execution_unavailable"
            )
            return TargetExecutionResult(False, reason)
        finally:
            connection.close()

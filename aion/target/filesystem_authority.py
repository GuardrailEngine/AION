"""Filesystem-backed target authority for Phase E.2."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


class TargetNotFoundError(FileNotFoundError):
    """Raised when the requested filesystem target does not exist."""


@dataclass(frozen=True)
class TargetRef:
    """Identity of a filesystem resource."""

    path: str


@dataclass(frozen=True)
class TargetSnapshot:
    """Immutable filesystem target state captured by the authority."""

    target_ref: TargetRef
    version: str
    content_hash: str
    source: str


class FileSystemTargetAuthority:
    """Read authoritative version and content state from the filesystem.

    Known limitation — TOCTOU window:
    Between ``snapshot()`` and the tool invocation in ``ExecutionBoundary``,
    the underlying file may change on disk. The version and content hash
    recorded at snapshot time therefore describe the state at issuance, not
    necessarily the state at execution. This is a deliberate, documented
    boundary of the current guarantee. Closing this window requires atomic
    compare-and-execute, which is explicitly out of scope.
    """

    def snapshot(self, action: str, target_ref: TargetRef) -> TargetSnapshot:
        """Return the current snapshot for ``target_ref``.

        ``action`` is part of the authority contract for future
        action-specific target semantics; the filesystem implementation does
        not currently vary its read behavior by action.
        """
        del action
        try:
            stat_result = os.stat(target_ref.path)
        except FileNotFoundError as exc:
            raise TargetNotFoundError(
                f"Filesystem target not found: {target_ref.path}"
            ) from exc

        with open(target_ref.path, "rb") as resource:
            content_hash = hashlib.sha256(resource.read()).hexdigest()

        return TargetSnapshot(
            target_ref=target_ref,
            version=str(stat_result.st_mtime_ns),
            content_hash=content_hash,
            source="filesystem",
        )

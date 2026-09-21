"""Import-compatible wrapper for the available AION Core snapshot.

The implementation remains in ``aion_core (1).py``.  This module only loads
that snapshot under a private module name and re-exports its public symbols so
legacy imports such as ``from aion_core import AgencyGate`` continue to work.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SNAPSHOT_PATH = Path(__file__).with_name("aion_core (1).py")
_SPEC = importlib.util.spec_from_file_location("_aion_core_snapshot", _SNAPSHOT_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - packaging error
    raise ImportError(f"Unable to load AION Core snapshot: {_SNAPSHOT_PATH}")

_SNAPSHOT = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _SNAPSHOT
_SPEC.loader.exec_module(_SNAPSHOT)

for _name, _value in vars(_SNAPSHOT).items():
    if not _name.startswith("_"):
        globals()[_name] = _value

__all__ = [
    _name for _name in vars(_SNAPSHOT)
    if not _name.startswith("_")
]

# Keep implementation details private in the wrapper namespace.
del _name, _value, _SPEC, _SNAPSHOT, _SNAPSHOT_PATH, importlib, Path, sys

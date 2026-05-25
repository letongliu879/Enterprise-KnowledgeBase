"""Indexing service skeleton."""

from __future__ import annotations

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[4]
_CONTRACTS_SRC = _ROOT / "packages" / "contracts" / "src"
_RAGFLOW_RUNTIME_SRC = _ROOT / "packages" / "ragflow_runtime" / "src"
if _CONTRACTS_SRC.exists():
    contracts_path = str(_CONTRACTS_SRC)
    if contracts_path not in sys.path:
        sys.path.insert(0, contracts_path)
if _RAGFLOW_RUNTIME_SRC.exists():
    ragflow_runtime_path = str(_RAGFLOW_RUNTIME_SRC)
    if ragflow_runtime_path not in sys.path:
        sys.path.insert(0, ragflow_runtime_path)

"""Compatibility alias for the shared RAGFlow converter."""

from __future__ import annotations

import sys

from intake_runtime.converters import ragflow_converter as _impl

sys.modules[__name__] = _impl

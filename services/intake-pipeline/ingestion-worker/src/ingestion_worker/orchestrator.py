"""Compatibility alias for the shared intake runtime orchestrator."""

from __future__ import annotations

import sys

from intake_runtime import orchestrator as _impl

sys.modules[__name__] = _impl

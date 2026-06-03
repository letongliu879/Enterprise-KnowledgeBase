"""Compatibility alias for the shared intake runtime reviewer."""

from __future__ import annotations

import sys

from intake_runtime import agent_reviewer as _impl

sys.modules[__name__] = _impl

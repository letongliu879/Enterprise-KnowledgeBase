"""Compatibility alias for the shared intake runtime lease service."""

from __future__ import annotations

import sys

from intake_runtime import lease_service as _impl

sys.modules[__name__] = _impl

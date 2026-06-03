"""Compatibility alias for shared stage adapters."""

from __future__ import annotations

import sys

from intake_runtime.stages import adapters as _impl

sys.modules[__name__] = _impl

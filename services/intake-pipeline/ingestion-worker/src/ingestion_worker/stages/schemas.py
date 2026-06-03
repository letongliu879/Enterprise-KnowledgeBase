"""Compatibility alias for shared stage schemas."""

from __future__ import annotations

import sys

from intake_runtime.stages import schemas as _impl

sys.modules[__name__] = _impl

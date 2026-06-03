"""Compatibility alias for shared stage protocol types."""

from __future__ import annotations

import sys

from intake_runtime.stages import protocol as _impl

sys.modules[__name__] = _impl

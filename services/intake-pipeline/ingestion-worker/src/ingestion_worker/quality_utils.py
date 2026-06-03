"""Compatibility alias for shared quality utilities."""

from __future__ import annotations

import sys

from intake_runtime import quality_utils as _impl

sys.modules[__name__] = _impl

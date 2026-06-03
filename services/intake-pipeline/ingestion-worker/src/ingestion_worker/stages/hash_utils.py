"""Compatibility alias for shared stage hash utilities."""

from __future__ import annotations

import sys

from intake_runtime.stages import hash_utils as _impl

sys.modules[__name__] = _impl

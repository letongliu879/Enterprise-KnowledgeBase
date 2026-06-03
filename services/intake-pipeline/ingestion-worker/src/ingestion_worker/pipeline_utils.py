"""Compatibility alias for shared pipeline utilities."""

from __future__ import annotations

import sys

from intake_runtime import pipeline_utils as _impl

sys.modules[__name__] = _impl

"""Compatibility alias for shared converter base types."""

from __future__ import annotations

import sys

from intake_runtime.converters import base as _impl

sys.modules[__name__] = _impl

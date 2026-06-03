"""Compatibility alias for shared index asset helpers."""

from __future__ import annotations

import sys

from intake_runtime import index_assets as _impl

sys.modules[__name__] = _impl

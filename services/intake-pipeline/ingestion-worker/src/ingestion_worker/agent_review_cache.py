"""Compatibility alias for the shared intake runtime review cache."""

from __future__ import annotations

import sys

from intake_runtime import agent_review_cache as _impl

sys.modules[__name__] = _impl

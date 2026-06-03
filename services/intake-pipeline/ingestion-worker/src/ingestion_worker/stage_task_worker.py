"""Compatibility alias for shared stage-task worker helpers."""

from __future__ import annotations

import sys

from intake_runtime import stage_task_worker as _impl

sys.modules[__name__] = _impl

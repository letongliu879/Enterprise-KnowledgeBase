"""Runtime policy helpers for split-service owner boundaries."""

from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def allow_local_fallback_for_tests() -> bool:
    raw = os.environ.get("ALLOW_LOCAL_FALLBACK_FOR_TESTS", "")
    return raw.strip().lower() in _TRUTHY


def require_explicit_owner_url(*, env_var: str, owner_name: str) -> None:
    if allow_local_fallback_for_tests():
        return
    raise RuntimeError(
        f"{env_var} is required; {owner_name} must run through its split-service owner. "
        "Set ALLOW_LOCAL_FALLBACK_FOR_TESTS=true only for tests or explicit compat smoke."
    )

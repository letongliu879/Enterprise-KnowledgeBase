"""Authentication for internal event ingestion endpoints.

Each downstream service has its own API key.
Workbench validates the X-Service-Key header against known keys.
"""

import os
import secrets
from typing import Literal

from fastapi import Header, HTTPException, Request

# Load keys from environment variables at import time.
# In production these should be injected via secret management.
SERVICE_KEYS: dict[str, str] = {
    "intake": os.environ.get("WORKBENCH_EVENT_KEY_INTAKE", ""),
    "approval": os.environ.get("WORKBENCH_EVENT_KEY_APPROVAL", ""),
    "indexing": os.environ.get("WORKBENCH_EVENT_KEY_INDEXING", ""),
}


def _verify_key(provided_key: str | None, expected_key: str) -> bool:
    if not provided_key or not expected_key:
        return False
    return secrets.compare_digest(provided_key.encode(), expected_key.encode())


async def verify_service_key(
    request: Request,
    x_service_key: str | None = Header(None, alias="X-Service-Key"),
) -> Literal["intake", "approval", "indexing"]:
    """Verify X-Service-Key and return the matched service name."""
    for service, expected in SERVICE_KEYS.items():
        if _verify_key(x_service_key, expected):
            # Also verify the URL path segment matches the key owner
            path_service = request.path_params.get("service")
            if path_service and path_service != service:
                raise HTTPException(status_code=403, detail="Service key does not match URL path")
            return service  # type: ignore[return-value]
    raise HTTPException(status_code=401, detail="Invalid or missing service key")

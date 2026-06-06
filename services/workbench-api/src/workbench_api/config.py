"""Workbench service configuration."""

import os


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class WorkbenchConfig:
    """Configuration loaded from environment variables."""

    jwt_secret: str = _require_env("JWT_SECRET")
    jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
    jwt_issuer: str = os.environ.get("JWT_ISSUER", "")
    jwt_audience: str = os.environ.get("JWT_AUDIENCE", "")
    auth_mode: str = os.environ.get("AUTH_MODE", "smoke")

    indexing_base_url: str = os.environ.get("INDEXING_BASE_URL", "http://127.0.0.1:18080")
    # Support both legacy INGESTION_WORKER_URL and deploy/.env INTAKE_BASE_URL
    ingestion_worker_url: str = os.environ.get("INGESTION_WORKER_URL") or os.environ.get("INTAKE_BASE_URL", "http://127.0.0.1:18085")
    approval_base_url: str = os.environ.get("APPROVAL_BASE_URL", "http://127.0.0.1:18087")
    admin_base_url: str = os.environ.get("ADMIN_BASE_URL", "http://127.0.0.1:18084")
    # Port 18181 matches deploy/.env ACCESS_BASE_URL
    access_base_url: str = os.environ.get("ACCESS_BASE_URL", "http://127.0.0.1:18181")
    document_service_base_url: str = os.environ.get("DOCUMENT_SERVICE_BASE_URL", "http://localhost:8006")
    # Support both legacy PUBLISHING_BASE_URL and deploy/.env PUBLISHING_WORKER_BASE_URL
    publishing_base_url: str = os.environ.get("PUBLISHING_BASE_URL") or os.environ.get("PUBLISHING_WORKER_BASE_URL", "http://127.0.0.1:18086")
    retrieval_base_url: str = os.environ.get("RETRIEVAL_BASE_URL", "http://127.0.0.1:18182")
    access_internal_api_key: str = os.environ.get("ACCESS_INTERNAL_API_KEY", "")

    # Event ingestion service keys (fallback to empty string = disabled)
    workbench_event_key_intake: str = os.environ.get("WORKBENCH_EVENT_KEY_INTAKE", "")
    workbench_event_key_approval: str = os.environ.get("WORKBENCH_EVENT_KEY_APPROVAL", "")
    workbench_event_key_indexing: str = os.environ.get("WORKBENCH_EVENT_KEY_INDEXING", "")

    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://user:pass@localhost/reality_rag",
    )

    default_http_timeout: float = float(os.environ.get("DEFAULT_HTTP_TIMEOUT", "30.0"))


config = WorkbenchConfig()

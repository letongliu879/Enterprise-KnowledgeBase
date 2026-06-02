"""Workbench service configuration."""

import os


class WorkbenchConfig:
    """Configuration loaded from environment variables."""

    jwt_secret: str = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
    jwt_issuer: str = os.environ.get("JWT_ISSUER", "")
    jwt_audience: str = os.environ.get("JWT_AUDIENCE", "")
    auth_mode: str = os.environ.get("AUTH_MODE", "smoke")

    indexing_base_url: str = os.environ.get("INDEXING_BASE_URL", "http://127.0.0.1:18080")
    intake_base_url: str = os.environ.get("INTAKE_BASE_URL", "http://127.0.0.1:18085")
    approval_base_url: str = os.environ.get("APPROVAL_BASE_URL", "http://127.0.0.1:18087")
    admin_base_url: str = os.environ.get("ADMIN_BASE_URL", "http://127.0.0.1:18084")
    access_base_url: str = os.environ.get("ACCESS_BASE_URL", "http://127.0.0.1:18081")
    document_service_base_url: str = os.environ.get("DOCUMENT_SERVICE_BASE_URL", "http://localhost:8006")
    access_internal_api_key: str = os.environ.get("ACCESS_INTERNAL_API_KEY", "")

    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://user:pass@localhost/reality_rag",
    )

    default_http_timeout: float = float(os.environ.get("DEFAULT_HTTP_TIMEOUT", "30.0"))


config = WorkbenchConfig()

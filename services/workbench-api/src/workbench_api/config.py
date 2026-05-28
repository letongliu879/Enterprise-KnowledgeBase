"""Workbench service configuration."""

import os


class WorkbenchConfig:
    """Configuration loaded from environment variables."""

    jwt_secret: str = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
    jwt_issuer: str = os.environ.get("JWT_ISSUER", "")
    jwt_audience: str = os.environ.get("JWT_AUDIENCE", "")
    auth_mode: str = os.environ.get("AUTH_MODE", "smoke")

    indexing_base_url: str = os.environ.get("INDEXING_BASE_URL", "http://localhost:8002")
    intake_base_url: str = os.environ.get("INTAKE_BASE_URL", "http://localhost:8003")
    approval_base_url: str = os.environ.get("APPROVAL_BASE_URL", "http://localhost:8004")
    admin_base_url: str = os.environ.get("ADMIN_BASE_URL", "http://localhost:8001")

    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://user:pass@localhost/reality_rag",
    )

    default_http_timeout: float = float(os.environ.get("DEFAULT_HTTP_TIMEOUT", "10.0"))


config = WorkbenchConfig()

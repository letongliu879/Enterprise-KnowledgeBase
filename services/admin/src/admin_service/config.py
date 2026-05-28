"""Admin service configuration."""

import os


class AdminConfig:
    jwt_secret: str = os.getenv("ADMIN_JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = int(os.getenv("ADMIN_JWT_EXPIRATION_HOURS", "24"))
    session_expiration_hours: int = int(os.getenv("ADMIN_SESSION_EXPIRATION_HOURS", "168"))
    jwt_issuer: str = os.getenv("ADMIN_JWT_ISSUER", "")
    jwt_audience: str = os.getenv("ADMIN_JWT_AUDIENCE", "")
    auth_mode: str = os.getenv("AUTH_MODE", "smoke")
    indexing_base_url: str = os.getenv("INDEXING_BASE_URL", "http://localhost:18082")
    retrieval_base_url: str = os.getenv("RETRIEVAL_BASE_URL", "http://localhost:18083")
    access_base_url: str = os.getenv("ACCESS_BASE_URL", "http://localhost:18081")
    publishing_worker_base_url: str = os.getenv("PUBLISHING_WORKER_BASE_URL", "http://localhost:18085")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///admin.db")


config = AdminConfig()

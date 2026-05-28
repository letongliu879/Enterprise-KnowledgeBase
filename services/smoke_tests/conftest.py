"""Shared fixtures for cross-service smoke tests.

Design:
- All Python services are mounted under a single combined ASGI app.
- httpx.AsyncClient and httpx.Client are patched to use ASGITransport(combined_app)
  when no explicit transport is provided, so cross-service HTTP calls route
  in-process without starting real servers.
- A shared SQLite file is used so Java services can also read the state.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Python path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(ROOT / "services" / "admin" / "src"))
sys.path.insert(0, str(ROOT / "services" / "workbench-api" / "src"))
sys.path.insert(0, str(ROOT / "services" / "indexing" / "src"))
sys.path.insert(0, str(ROOT / "services" / "intake-pipeline" / "src"))
sys.path.insert(0, str(ROOT / "services" / "intake-pipeline" / "approval-service" / "src"))
sys.path.insert(0, str(ROOT / "services" / "intake-pipeline" / "publishing-worker" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "contracts" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "persistence" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "ragflow_runtime" / "src"))

# ---------------------------------------------------------------------------
# Environment variables (must be set BEFORE service modules are imported)
# ---------------------------------------------------------------------------
SMOKE_DB = ROOT / ".verify" / "runtime" / "smoke-test.db"
SMOKE_DB.parent.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{SMOKE_DB}"
os.environ["ADMIN_JWT_SECRET"] = "smoke-test-secret"
os.environ["ADMIN_JWT_ALGORITHM"] = "HS256"
os.environ["JWT_SECRET"] = "smoke-test-secret"
os.environ["JWT_ALGORITHM"] = "HS256"

# Base URLs for cross-service routing (must match combined app mounts)
os.environ["INDEXING_BASE_URL"] = "http://testserver/indexing"
os.environ["INTAKE_BASE_URL"] = "http://testserver/intake"
os.environ["APPROVAL_BASE_URL"] = "http://testserver/approval"
os.environ["ADMIN_BASE_URL"] = "http://testserver/admin"
os.environ["RETRIEVAL_BASE_URL"] = "http://testserver/retrieval"
os.environ["PUBLISHING_WORKER_BASE_URL"] = "http://testserver/publishing"
os.environ["REALITY_RAG_INDEXING_BASE_URL"] = "http://testserver/indexing"
os.environ["REALITY_RAG_INTAKE_RUNTIME_DIR"] = str(ROOT / ".verify" / "runtime" / "intake-smoke")

# Disable live model calls
for key in (
    "INDEXING_CHAT_API_KEY",
    "INDEXING_CHAT_BASE_URL",
    "INDEXING_CHAT_MODEL",
    "INDEXING_EMBEDDING_API_KEY",
    "INDEXING_EMBEDDING_BASE_URL",
    "INDEXING_EMBEDDING_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_MODEL",
):
    os.environ.pop(key, None)

# ---------------------------------------------------------------------------
# httpx patch: inject ASGITransport(combined_app) when no transport provided
# ---------------------------------------------------------------------------
from fastapi import FastAPI

combined_app = FastAPI(title="Reality-RAG Combined Smoke App")

_original_async_init = httpx.AsyncClient.__init__
_original_sync_init = httpx.Client.__init__


class _AsyncClientWrapper:
    """Sync-looking wrapper around httpx.AsyncClient + ASGITransport.

    intake_pipeline uses sync ``httpx.Client`` inside thread-pool workers.
    Those threads have no running event loop, so ``asyncio.run`` is safe.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.ASGITransport(app=combined_app)
        self._client = httpx.AsyncClient(*args, **kwargs)

    def __enter__(self):
        self._run(self._client.__aenter__())
        return self

    def __exit__(self, *args: Any):
        self._run(self._client.__aexit__(*args))

    def _run(self, coro):
        import asyncio
        import threading
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # Nested inside a running loop — offload to a fresh thread with explicit loop
        result: list = []
        exc: list = []
        def _runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result.append(loop.run_until_complete(coro))
            except Exception as e:
                exc.append(e)
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        t = threading.Thread(target=_runner)
        t.start()
        t.join()
        if exc:
            raise exc[0]
        return result[0]

    def post(self, *args: Any, **kwargs: Any):
        return self._run(self._client.post(*args, **kwargs))

    def get(self, *args: Any, **kwargs: Any):
        return self._run(self._client.get(*args, **kwargs))


def _patched_async_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
    if kwargs.get("transport") is None and kwargs.get("app") is None:
        kwargs["transport"] = httpx.ASGITransport(app=combined_app)
    _original_async_init(self, *args, **kwargs)


httpx.AsyncClient.__init__ = _patched_async_init  # type: ignore[assignment]

# Patch intake_pipeline's sync httpx.Client usage only (runs in thread pool)
import intake_pipeline.main as _intake_main  # noqa: E402

class _HttpxModuleProxy:
    """Proxy that replaces httpx.Client locally for intake_pipeline without mutating the global httpx module."""
    def __init__(self, real_httpx):
        object.__setattr__(self, '_real', real_httpx)
    def __getattr__(self, name):
        return getattr(self._real, name)
    @property
    def Client(self):
        return _AsyncClientWrapper

_intake_main.httpx = _HttpxModuleProxy(httpx)  # type: ignore[misc]

# ---------------------------------------------------------------------------
# Import and mount service apps
# ---------------------------------------------------------------------------
from admin_service.main import app as admin_app
from workbench_api.main import app as workbench_app
from indexing_service.main import app as indexing_app
from intake_pipeline.main import app as intake_app
from approval_service.main import app as approval_app
from publishing_worker.main import app as publishing_app

class _PrefixApp:
    """ASGI wrapper that prepends a path prefix after mount stripping."""

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope)
            scope["path"] = self.prefix + scope["path"]
            raw = scope.get("raw_path")
            if raw is not None:
                scope["raw_path"] = self.prefix.encode() + raw
        await self.app(scope, receive, send)


# Specific mounts first, catch-all last.
# workbench routes embed /workbench — use prefix wrapper so mount strip + re-add = original path.
combined_app.mount("/workbench", _PrefixApp(workbench_app, "/workbench"))
combined_app.mount("/indexing", indexing_app)
combined_app.mount("/intake", intake_app)
combined_app.mount("/approval", approval_app)
combined_app.mount("/publishing", publishing_app)
# admin routes embed /admin, and it has /health — mount at / so no stripping occurs.
combined_app.mount("/", admin_app)

# ---------------------------------------------------------------------------
# Database reset fixture
# ---------------------------------------------------------------------------
from reality_rag_persistence.database import create_all, drop_all, override_url_for_testing


@pytest.fixture(scope="module", autouse=True)
def _reset_smoke_db():
    override_url_for_testing(f"sqlite:///{SMOKE_DB}")
    drop_all()
    create_all()
    yield
    # Keep DB after test for Java verification; clean up at next test start


# ---------------------------------------------------------------------------
# JWT helper
# ---------------------------------------------------------------------------
import jwt


def _make_token(
    user_id: str,
    email: str = "smoke@test.com",
    roles: list[str] | None = None,
    tenant_id: str = "tenant_smoke",
    allowed_collections: list[str] | None = None,
    secret: str = "smoke-test-secret",
) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "roles": roles or [],
            "tenant_id": tenant_id,
            "allowed_collections": allowed_collections or [],
        },
        secret,
        algorithm="HS256",
    )


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _make_token("admin_01", roles=["knowledge_admin", "platform_admin"])


@pytest.fixture(scope="module")
def uploader_token() -> str:
    return _make_token("uploader_01", roles=["uploader"], allowed_collections=["col_smoke"])


# ---------------------------------------------------------------------------
# TestClient fixture
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(combined_app)


# ---------------------------------------------------------------------------
# Convenience: auth headers
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def uploader_headers(uploader_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {uploader_token}"}

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
# Environment variables (must be set BEFORE service modules are imported)
# ---------------------------------------------------------------------------
SMOKE_DB = ROOT / ".verify" / "runtime" / "smoke-test.db"
SMOKE_DB.parent.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{SMOKE_DB}"
os.environ["ADMIN_JWT_SECRET"] = "smoke-test-secret"
os.environ["ADMIN_JWT_ALGORITHM"] = "HS256"
os.environ["JWT_SECRET"] = "smoke-test-secret"
os.environ["JWT_ALGORITHM"] = "HS256"

os.environ["REALITY_RAG_INTAKE_RUNTIME_DIR"] = str(ROOT / ".verify" / "runtime" / "intake-smoke")
os.environ["REALITY_RAG_SIDECAR_DIR"] = str(ROOT / ".verify" / "runtime" / "sidecar-smoke")

os.environ["ALLOW_LOCAL_FALLBACK_FOR_TESTS"] = "true"



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

# NOTE: Service-URL env vars (INDEXING_BASE_URL, etc.) are NOT set at module
# level. They are set inside _apply_smoke_patches so that service modules
# imported during collection (see below) create config singletons with
# default (non-testserver) values. The fixture overrides them before any test
# runs and restores them afterward.



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


class _SyncHttpxModuleProxy:
    """Proxy that replaces httpx.Client locally for document_service_client without mutating the global httpx module."""
    def __init__(self, real_httpx):
        object.__setattr__(self, '_real', real_httpx)
    def __getattr__(self, name):
        return getattr(self._real, name)
    def _call(self, method: str, *args: Any, **kwargs: Any):
        wrapper = _AsyncClientWrapper(timeout=kwargs.pop("timeout", 30.0))
        try:
            return getattr(wrapper, method)(*args, **kwargs)
        finally:
            wrapper._run(wrapper._client.aclose())
    def post(self, *args: Any, **kwargs: Any):
        return self._call("post", *args, **kwargs)
    def get(self, *args: Any, **kwargs: Any):
        return self._call("get", *args, **kwargs)


_httpx_api = httpx  # reference to real module


def _patched_httpx_request(method, url, **kwargs):
    """Sync-looking wrapper that dispatches through AsyncClient+ASGITransport.

    Only intercepts URLs targeting the smoke-test in-process server (testserver).
    All other URLs fall through to the real httpx functions so unit tests that
    use external URLs are not affected.
    """
    url_str = str(url)
    if "testserver" not in url_str:
        return getattr(_httpx_api, method.lower())(url, **kwargs)
    timeout = kwargs.pop("timeout", 30.0)
    wrapper = _AsyncClientWrapper(timeout=timeout)
    try:
        return wrapper._run(wrapper._client.request(method, url, **kwargs))
    finally:
        wrapper._run(wrapper._client.aclose())


def _patched_httpx_get(url, **kwargs):
    return _patched_httpx_request("GET", url, **kwargs)


def _patched_httpx_post(url, **kwargs):
    return _patched_httpx_request("POST", url, **kwargs)


def _patched_httpx_put(url, **kwargs):
    return _patched_httpx_request("PUT", url, **kwargs)


def _patched_httpx_patch(url, **kwargs):
    return _patched_httpx_request("PATCH", url, **kwargs)


def _patched_httpx_delete(url, **kwargs):
    return _patched_httpx_request("DELETE", url, **kwargs)


def _patched_workbench_events_url(service: str) -> str | None:
    return f"http://testserver/internal/events/{service}"


@pytest.fixture(scope="module", autouse=True)
def _apply_smoke_patches():
    """Apply httpx patches only when running smoke tests."""
    def _patched_async_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("transport") is None and kwargs.get("app") is None:
            kwargs["transport"] = httpx.ASGITransport(app=combined_app)
        _original_async_init(self, *args, **kwargs)

    httpx.AsyncClient.__init__ = _patched_async_init  # type: ignore[assignment]

    # Patch document_service_client sync httpx usage for in-process smoke tests
    import ingestion_worker.document_service_client as _document_service_client_mod  # noqa: E402
    _document_service_client_mod.httpx = _SyncHttpxModuleProxy(httpx)  # type: ignore[misc]

    # Patch ingestion_worker outbox_deliver for in-process smoke tests
    import ingestion_worker.outbox_deliver as _outbox_deliver_mod  # noqa: E402
    _outbox_deliver_mod.httpx = _SyncHttpxModuleProxy(httpx)  # type: ignore[misc]

    # Patch httpx top-level API functions
    httpx.get = _patched_httpx_get
    httpx.post = _patched_httpx_post
    httpx.put = _patched_httpx_put
    httpx.patch = _patched_httpx_patch
    httpx.delete = _patched_httpx_delete
    httpx.request = _patched_httpx_request

    # Patch _workbench_events_url
    _outbox_deliver_mod._workbench_events_url = _patched_workbench_events_url  # type: ignore[misc]

    # Set cross-service routing env vars for the combined app
    _smoke_env = {
        "INDEXING_BASE_URL": "http://testserver/indexing",
        "INTAKE_BASE_URL": "http://testserver/intake",
        "APPROVAL_BASE_URL": "http://testserver/approval",
        "ADMIN_BASE_URL": "http://testserver/admin",
        "RETRIEVAL_BASE_URL": "http://testserver/retrieval",
        "PUBLISHING_WORKER_BASE_URL": "http://testserver/publishing",
        "PUBLISHING_BASE_URL": "http://testserver/publishing",
        "REALITY_RAG_INDEXING_BASE_URL": "http://testserver/indexing",
        "DOCUMENT_SERVICE_BASE_URL": "http://testserver/documents",
        "DOCUMENT_SERVICE_URL": "http://testserver/documents",
        "APPROVAL_SERVICE_URL": "http://testserver/approval",
        "INDEXING_SERVICE_URL": "http://testserver/indexing",
        "WORKBENCH_BASE_URL": "http://testserver/workbench",
        "WORKBENCH_EVENT_KEY_INTAKE": "smoke-intake-key",
        "WORKBENCH_EVENT_KEY_APPROVAL": "smoke-approval-key",
        "WORKBENCH_EVENT_KEY_INDEXING": "smoke-indexing-key",
    }
    _old_env = {}
    for _key, _val in _smoke_env.items():
        _old_env[_key] = os.environ.get(_key)
        os.environ[_key] = _val

    # Force-override service configs to match the combined in-process app
    # regardless of import order from other test modules.
    from admin_service.config import config as _admin_config
    _orig_admin_config = {
        "jwt_secret": _admin_config.jwt_secret,
        "indexing_base_url": _admin_config.indexing_base_url,
        "retrieval_base_url": _admin_config.retrieval_base_url,
        "access_base_url": _admin_config.access_base_url,
        "publishing_worker_base_url": _admin_config.publishing_worker_base_url,
    }
    _admin_config.jwt_secret = "smoke-test-secret"
    _admin_config.indexing_base_url = "http://testserver/indexing"
    _admin_config.retrieval_base_url = "http://testserver/retrieval"
    _admin_config.access_base_url = "http://testserver/access"
    _admin_config.publishing_worker_base_url = "http://testserver/publishing"

    from workbench_api.config import config as _workbench_config
    _orig_workbench_config = {
        "indexing_base_url": _workbench_config.indexing_base_url,
        "ingestion_worker_url": _workbench_config.ingestion_worker_url,
        "approval_base_url": _workbench_config.approval_base_url,
        "admin_base_url": _workbench_config.admin_base_url,
        "access_base_url": _workbench_config.access_base_url,
        "document_service_base_url": _workbench_config.document_service_base_url,
        "publishing_base_url": _workbench_config.publishing_base_url,
        "workbench_event_key_intake": _workbench_config.workbench_event_key_intake,
        "workbench_event_key_approval": _workbench_config.workbench_event_key_approval,
        "workbench_event_key_indexing": _workbench_config.workbench_event_key_indexing,
    }
    _workbench_config.indexing_base_url = "http://testserver/indexing"
    _workbench_config.ingestion_worker_url = "http://testserver/intake"
    _workbench_config.approval_base_url = "http://testserver/approval"
    _workbench_config.admin_base_url = "http://testserver/admin"
    _workbench_config.access_base_url = "http://testserver/access"
    _workbench_config.document_service_base_url = "http://testserver/documents"
    _workbench_config.publishing_base_url = "http://testserver/publishing"
    _workbench_config.workbench_event_key_intake = "smoke-intake-key"
    _workbench_config.workbench_event_key_approval = "smoke-approval-key"
    _workbench_config.workbench_event_key_indexing = "smoke-indexing-key"

    yield

    # Teardown: restore original config values
    for _attr, _val in _orig_admin_config.items():
        setattr(_admin_config, _attr, _val)
    for _attr, _val in _orig_workbench_config.items():
        setattr(_workbench_config, _attr, _val)

    # Teardown: restore original httpx functions
    httpx.AsyncClient.__init__ = _original_async_init  # type: ignore[assignment]
    httpx.get = _httpx_api.get
    httpx.post = _httpx_api.post
    httpx.put = _httpx_api.put
    httpx.patch = _httpx_api.patch
    httpx.delete = _httpx_api.delete
    httpx.request = _httpx_api.request

    # Restore env vars (captured at fixture setup, before smoke overrides)
    for _key, _old_val in _old_env.items():
        if _old_val is None:
            os.environ.pop(_key, None)
        else:
            os.environ[_key] = _old_val

# ---------------------------------------------------------------------------
# Import and mount service apps
# ---------------------------------------------------------------------------
from admin_service.main import app as admin_app
from workbench_api.main import app as workbench_app
from indexing_service.main import app as indexing_app
from document_service.main import app as document_app
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
combined_app.mount("/documents", document_app)
combined_app.mount("/approval", approval_app)
combined_app.mount("/publishing", publishing_app)

# Direct-mount workbench event routes at /internal/events for cross-service event forwarding
# Must be before catch-all admin mount
from workbench_api.events import router as _events_router  # noqa: E402
combined_app.include_router(_events_router)

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
from jose import jwt


def _make_token(
    user_id: str,
    email: str = "smoke@test.com",
    roles: list[str] | None = None,
    tenant_id: str = "tenant_smoke",
    allowed_collections: list[str] | None = None,
) -> str:
    # Read secret from the actual admin config at call time to avoid
    # import-order races with other test modules that may import
    # admin_service.config before ADMIN_JWT_SECRET is set in the env.
    from admin_service.config import config as _admin_config
    secret = _admin_config.jwt_secret
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
    with TestClient(combined_app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Convenience: auth headers
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def uploader_headers(uploader_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {uploader_token}"}


@pytest.fixture(scope="module")
def reviewer_token() -> str:
    return _make_token("reviewer_01", roles=["reviewer"], allowed_collections=["col_smoke"])


@pytest.fixture(scope="module")
def reviewer_headers(reviewer_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {reviewer_token}"}


class _FakeSmokeReviewerConfig:
    model = "smoke-reviewer"
    prompt_version = "smoke"
    artifact_schema_version = "v2"


class _FakeSmokeReviewer:
    def __init__(self) -> None:
        self._config = _FakeSmokeReviewerConfig()

    def review(self, *, doc_id: str, canonical_content: str, quality_report, event_hook=None):
        from reality_rag_contracts import AgentReview, PublishStatus, ReviewDecision

        if event_hook is not None:
            event_hook(
                event_type="review.started",
                payload={
                    "model": self._config.model,
                    "prompt_excerpt": "smoke fake reviewer",
                    "canonical_excerpt": canonical_content[:200],
                },
            )
        review = AgentReview(
            doc_id=doc_id,
            decision=ReviewDecision.APPROVE,
            confidence=0.99,
            reasons=["smoke auto-approve"],
            risk_tags=[],
            suggested_actions=[],
            publish_recommendation=PublishStatus.PUBLISHED,
            sections_requiring_review=[],
            document_type="policy",
            suggested_authority_level=5,
            detected_pii=[],
            diff_summary="smoke fake review",
            anchored_findings=[],
        )
        if event_hook is not None:
            event_hook(
                event_type="review.completed",
                payload=review.model_dump(mode="json"),
            )
        review._llm_call_records = []  # type: ignore[attr-defined]
        return review


def _build_real_chain_pipeline():
    from ingestion_worker.pipeline import IngestionPipeline
    from intake_runtime.agent_review_cache import get_agent_review_cache
    from intake_runtime.converters.ragflow_converter import RAGFlowConverter

    # Patch RAGFlowConverter to avoid real HTTP calls in smoke tests
    def _fake_parse_via_indexing(self, command: dict) -> tuple[dict, dict]:
        from indexing_service.repository import create_indexing_repository
        from reality_rag_contracts.indexing_models import ParseSnapshotRecord

        source_file_id = command.get("source_file_id", "fake")
        parse_snapshot_id = f"snap_{source_file_id}"
        tenant_id = command.get("tenant_id", "default")
        collection_id = command.get("collection_id", "default")

        # Persist snapshot so indexing service can look it up later
        repo = create_indexing_repository()
        repo.save_parse_snapshot(
            ParseSnapshotRecord(
                parse_snapshot_id=parse_snapshot_id,
                request_id=command.get("request_id", f"req_{source_file_id}"),
                tenant_id=tenant_id,
                collection_id=collection_id,
                source_file_id=source_file_id,
                source_binary_ref=command.get("source_binary_ref", ""),
                source_filename=command.get("filename", "real-chain.md"),
                source_suffix="md",
                parser_id="naive",
                parser_backend="naive",
                parser_profile_id=command.get("collection_id", "default"),
                chunk_profile_id="default",
                document_family="markdown",
                effective_policy="smoke-policy",
                collection_parser_config={},
                parser_config={"chunk_token_num": 128},
                input_hash="sha256:fake",
                preview_text="# Real Chain\n\nHello world\n",
                upstream_chunks=[
                    {
                        "chunk_id": "chunk_1",
                        "content_with_weight": "# Real Chain",
                        "position_int": [0],
                    },
                    {
                        "chunk_id": "chunk_2",
                        "content_with_weight": "Hello world",
                        "position_int": [1],
                    },
                ],
                outline=[],
                document_metadata={},
                chunk_preview=[],
                warnings=[],
                decision_reason="smoke-pass",
            )
        )

        return (
            {
                "parse_snapshot_id": parse_snapshot_id,
                "parser_id": "naive",
                "status": "completed",
            },
            {
                "parse_snapshot_id": parse_snapshot_id,
                "preview_text": "# Real Chain\n\nHello world\n",
                "upstream_chunks": [
                    {"content_with_weight": "# Real Chain"},
                    {"content_with_weight": "Hello world"},
                ],
                "parser_id": "naive",
                "parser_profile_id": command.get("collection_id", "default"),
                "document_family": "markdown",
                "source_suffix": "md",
            },
        )

    RAGFlowConverter._parse_via_indexing = _fake_parse_via_indexing  # type: ignore[assignment]

    return IngestionPipeline(
        converters=[RAGFlowConverter()],
        agent_reviewer=_FakeSmokeReviewer(),
        agent_review_cache=get_agent_review_cache(),
        telemetry_store=None,
    )


def _source_file_jobs_are_terminal(source_file_ids: list[str]) -> bool:
    from reality_rag_contracts import IntakeJobState
    from reality_rag_persistence.database import get_session
    from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository

    session = get_session()
    try:
        repo = IntakeJobRepository(session)
        for source_file_id in source_file_ids:
            job = repo.get_by_source_file_id(source_file_id)
            if job is None or job.state not in {
                IntakeJobState.PUBLISHED.value,
                IntakeJobState.REJECTED.value,
                IntakeJobState.FAILED.value,
                IntakeJobState.CANCELLED.value,
                IntakeJobState.EXPIRED.value,
                IntakeJobState.AWAITING_APPROVAL.value,
            }:
                return False
        return True
    finally:
        session.close()


def drain_real_chain_for_source_files(source_file_ids: list[str], *, max_rounds: int = 40) -> None:
    """Drive the split-owner intake chain to a terminal state in-process.

    This is the in-process real-chain smoke harness for document-service ->
    FileReady -> orchestrator -> stage workers. It intentionally avoids the
    compat root `/v1/documents` path.
    """

    from reality_rag_contracts import StageName
    from reality_rag_persistence.database import get_session
    from reality_rag_persistence.outbox import OutboxDispatcher

    from ingestion_worker.domains.publishing_domain import persist_document_and_policy
    from ingestion_worker.outbox_deliver import make_deliver_callback
    from intake_runtime.stage_runtime import (
        execute_conversion_task,
        execute_publishing_task,
        execute_review_task,
    )
    from intake_runtime.stage_task_worker import make_stage_task_deliver, make_stage_task_filter

    pipeline = _build_real_chain_pipeline()
    orchestrator_dispatcher = OutboxDispatcher(
        session_factory=get_session,
        deliver=make_deliver_callback(),
        should_process=lambda event: event.event_type != "StageTaskRequested",
        batch_size=100,
    )
    conversion_dispatcher = OutboxDispatcher(
        session_factory=get_session,
        deliver=make_stage_task_deliver(
            stage_name=StageName.CONVERSION,
            consumer_id="conversion-worker:stage-task:smoke",
            worker_id="worker-conversion-smoke",
            execute=lambda session, stage_task_id, intake_job_id, worker_id: execute_conversion_task(
                session,
                stage_task_id,
                intake_job_id,
                pipeline,
                worker_id,
            ),
        ),
        should_process=make_stage_task_filter(StageName.CONVERSION),
        batch_size=100,
    )
    review_dispatcher = OutboxDispatcher(
        session_factory=get_session,
        deliver=make_stage_task_deliver(
            stage_name=StageName.AGENT_REVIEW,
            consumer_id="agent-review-worker:stage-task:smoke",
            worker_id="worker-agent-review-smoke",
            execute=lambda session, stage_task_id, intake_job_id, worker_id: execute_review_task(
                session,
                stage_task_id,
                intake_job_id,
                pipeline,
                worker_id,
            ),
        ),
        should_process=make_stage_task_filter(StageName.AGENT_REVIEW),
        batch_size=100,
    )
    publishing_dispatcher = OutboxDispatcher(
        session_factory=get_session,
        deliver=make_stage_task_deliver(
            stage_name=StageName.PUBLISHING,
            consumer_id="publishing-worker:stage-task:smoke",
            worker_id="worker-publishing-smoke",
            execute=lambda session, stage_task_id, intake_job_id, worker_id: execute_publishing_task(
                session,
                stage_task_id,
                intake_job_id,
                worker_id,
                persist_fn=persist_document_and_policy,
            ),
        ),
        should_process=make_stage_task_filter(StageName.PUBLISHING),
        batch_size=100,
    )

    for _ in range(max_rounds):
        orchestrator_dispatcher.poll_and_dispatch()
        conversion_dispatcher.poll_and_dispatch()
        review_dispatcher.poll_and_dispatch()
        publishing_dispatcher.poll_and_dispatch()
        orchestrator_dispatcher.poll_and_dispatch()
        if _source_file_jobs_are_terminal(source_file_ids):
            return

    raise AssertionError(f"Real-chain smoke did not reach terminal state for source files: {source_file_ids}")


def reconcile_workbench_tasks(*, limit: int = 100) -> dict[str, Any]:
    import asyncio

    from reality_rag_persistence.database import get_session

    from workbench_api.downstream_clients import ApprovalClient, IndexingClient, IntakeClient
    from workbench_api.projections.reconciler import ProjectionReconciler

    session = get_session()
    try:
        reconciler = ProjectionReconciler(
            session=session,
            intake_client=IntakeClient(),
            approval_client=ApprovalClient(),
            indexing_client=IndexingClient(),
        )
        result = asyncio.run(reconciler.reconcile_tasks(limit=limit))
        session.commit()
        return result
    finally:
        session.close()

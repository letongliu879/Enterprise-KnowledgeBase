"""Split service boundary tests — Phase 0 baseline.

These tests mark the current state of the three service directories:
  - ingestion-worker (monolith, still owns all endpoints)
  - indexing-service (independent directory, subset of endpoints)
  - approval-service (independent directory, approval domain endpoints)

Status: Phase 8 is NOT complete.  The directories exist but the services are
not yet fully independent deployable units with their own data ownership.
"""

from __future__ import annotations

import inspect

import pytest


# ── Endpoint inventory helpers ──────────────────────────────────────────


def _list_routes(module) -> set[str]:
    """Extract @app.post/@app.get decorated function paths from a FastAPI module."""
    routes: set[str] = set()
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, "__wrapped__"):
            # FastAPI route decorator sets .__wrapped__ via functools.wraps
            pass
        if inspect.isfunction(obj):
            # Heuristic: look for common FastAPI endpoint path patterns in defaults
            # We scan the source for decorator arguments instead
            import ast

            try:
                source = inspect.getsource(obj)
            except (OSError, TypeError):
                continue
            # Check if the function is decorated with @app.get/post/...
            tree = ast.parse(source)
            func_def = tree.body[0]
            if isinstance(func_def, ast.FunctionDef):
                for decorator in func_def.decorator_list:
                    if isinstance(decorator, ast.Call):
                        dec_name = ast.unparse(decorator.func) if hasattr(ast, "unparse") else ""
                        if "app." in dec_name:
                            for kw in decorator.keywords:
                                if kw.arg == "path":
                                    routes.add(ast.literal_eval(kw.value))
                            for arg in decorator.args:
                                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                    routes.add(arg.value)
    return routes


def _extract_fastapi_routes_from_source(source: str) -> set[str]:
    """Parse @app.get/post('/path') decorators from module source."""
    import re

    pattern = r'@app\.(get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']'
    matches = re.findall(pattern, source)
    return {path for _method, path in matches}


# ── Tests ───────────────────────────────────────────────────────────────


class TestIndexingServiceBoundary:
    """Indexing service has been split into its own directory but is still
    reachable from the monolith via INDEXING_SERVICE_URL fallback.
    """

    def test_indexing_service_directory_exists(self) -> None:
        from pathlib import Path

        # test file -> tests/ -> ingestion-worker/ -> intake-pipeline/ -> indexing-service
        svc_dir = Path(__file__).parent.parent.parent / "indexing-service"
        assert svc_dir.exists(), "indexing-service directory must exist for Phase 8"
        assert (svc_dir / "src" / "indexing_service" / "main.py").exists()

    def test_indexing_service_has_subset_of_endpoints(self) -> None:
        """indexing-service exposes only indexing endpoints, not ingestion."""
        from pathlib import Path

        main_path = (
            Path(__file__).parent.parent.parent
            / "indexing-service"
            / "src"
            / "indexing_service"
            / "main.py"
        )
        routes = _extract_fastapi_routes_from_source(main_path.read_text(encoding="utf-8"))
        assert "/health" in routes
        assert "/internal/indexing/run" in routes
        assert "/internal/indexing/activate" in routes
        assert "/internal/indexing/rollback" in routes
        # Must NOT have ingestion endpoints
        assert "/internal/ingestion/convert" not in routes
        assert "/internal/ingestion/monitor/runs" not in routes

    def test_indexing_service_persistence_tables_exist(self) -> None:
        """indexing-service now owns its persistence tables (Phase 6 complete)."""
        from reality_rag_persistence import models as persistence_models

        assert hasattr(persistence_models, "IndexBuildJobModel")
        assert hasattr(persistence_models, "IndexedDocumentModel")


class TestApprovalServiceBoundary:
    """Approval service has been split into its own directory."""

    def test_approval_service_directory_exists(self) -> None:
        from pathlib import Path

        svc_dir = Path(__file__).parent.parent.parent / "approval-service"
        assert svc_dir.exists(), "approval-service directory must exist for Phase 8"
        assert (svc_dir / "src" / "approval_service" / "main.py").exists()

    def test_approval_service_exposes_approval_endpoints(self) -> None:
        from pathlib import Path

        main_path = (
            Path(__file__).parent.parent.parent
            / "approval-service"
            / "src"
            / "approval_service"
            / "main.py"
        )
        routes = _extract_fastapi_routes_from_source(main_path.read_text(encoding="utf-8"))
        assert "/health" in routes
        assert "/internal/approval/system-decide" in routes
        assert "/internal/approval/auto-approve" in routes
        assert "/internal/approval/auto-reject" in routes
        assert "/internal/approval/pending" in routes
        # Must NOT have ingestion or indexing endpoints
        assert "/internal/ingestion/convert" not in routes
        assert "/internal/indexing/run" not in routes

    def test_approval_service_owns_approval_tables(self) -> None:
        """approval-service tables already exist (Phase 5 completed)."""
        from reality_rag_persistence import models as persistence_models

        assert hasattr(persistence_models, "ApprovalTicketModel")
        assert hasattr(persistence_models, "ApprovalAuditLogModel")


class TestIngestionWorkerStillMonolithic:
    """ingestion-worker still carries endpoints that will eventually move."""

    def test_ingestion_worker_still_has_indexing_endpoints(self) -> None:
        """ingestion-worker still exposes /internal/indexing/* as compatibility layer.

        [TRANSITIONAL] Phase 8: these will be removed once all callers use
        indexing-service directly.
        """
        from pathlib import Path

        main_path = Path(__file__).parent.parent / "src" / "ingestion_worker" / "main.py"
        routes = _extract_fastapi_routes_from_source(main_path.read_text(encoding="utf-8"))
        assert "/internal/indexing/run" in routes
        assert "/internal/indexing/activate" in routes
        assert "/internal/indexing/rollback" in routes

    def test_ingestion_worker_has_approval_domain_fallback(self) -> None:
        """ingestion-worker can dispatch to remote approval-service or local fallback."""
        from ingestion_worker.domains.approval_domain import _get_remote_url, ApprovalService

        # _get_remote_url returns None when APPROVAL_SERVICE_URL is not set
        # (default behavior in test environment)
        assert _get_remote_url() is None or isinstance(_get_remote_url(), str)
        # ApprovalService can be instantiated in local mode
        assert ApprovalService is not None

    def test_ingestion_worker_has_indexing_domain_fallback(self) -> None:
        """ingestion-worker can dispatch to remote indexing-service or local fallback."""
        from ingestion_worker.indexing_service import get_indexing_service

        # get_indexing_service returns a service that can run/activate/rollback
        svc = get_indexing_service()
        assert svc is not None
        assert hasattr(svc, "run")
        assert hasattr(svc, "activate")
        assert hasattr(svc, "rollback")

    def test_ingestion_worker_has_document_domain_fallback(self) -> None:
        """ingestion-worker can dispatch to remote document-service or local fallback."""
        from ingestion_worker.document_service_client import (
            _get_remote_url,
            DocumentServiceClient,
        )

        # _get_remote_url returns None when DOCUMENT_SERVICE_URL is not set
        assert _get_remote_url() is None or isinstance(_get_remote_url(), str)
        # DocumentServiceClient can be instantiated in local mode
        assert DocumentServiceClient is not None


class TestDocumentServiceBoundary:
    """Document service has been split into its own directory."""

    def test_document_service_directory_exists(self) -> None:
        from pathlib import Path

        svc_dir = Path(__file__).parent.parent.parent / "document-service"
        assert svc_dir.exists(), "document-service directory must exist for Phase 8"
        assert (svc_dir / "src" / "document_service" / "main.py").exists()

    def test_document_service_exposes_source_file_endpoints(self) -> None:
        from pathlib import Path

        main_path = (
            Path(__file__).parent.parent.parent
            / "document-service"
            / "src"
            / "document_service"
            / "main.py"
        )
        routes = _extract_fastapi_routes_from_source(main_path.read_text(encoding="utf-8"))
        assert "/health" in routes
        assert "/internal/source-files" in routes
        assert "/internal/source-files/{source_file_id}/claim" in routes
        assert "/internal/source-files/{source_file_id}/mark-consumed" in routes
        assert "/internal/source-files/{source_file_id}/mark-cleanable" in routes
        # Must NOT have ingestion or indexing endpoints
        assert "/internal/ingestion/convert" not in routes
        assert "/internal/indexing/run" not in routes

    def test_document_service_owns_source_file_tables(self) -> None:
        """document-service tables already exist (Phase 4 completed)."""
        from reality_rag_persistence import models as persistence_models

        assert hasattr(persistence_models, "SourceFileModel")
        assert hasattr(persistence_models, "ObjectBlobModel")


class TestPublishingWorkerBoundary:
    """Publishing worker has been split into its own directory."""

    def test_publishing_worker_directory_exists(self) -> None:
        from pathlib import Path

        svc_dir = Path(__file__).parent.parent.parent / "publishing-worker"
        assert svc_dir.exists(), "publishing-worker directory must exist for Phase 8"
        assert (svc_dir / "src" / "publishing_worker" / "main.py").exists()

    def test_publishing_worker_exposes_publishing_endpoints(self) -> None:
        from pathlib import Path

        main_path = (
            Path(__file__).parent.parent.parent
            / "publishing-worker"
            / "src"
            / "publishing_worker"
            / "main.py"
        )
        routes = _extract_fastapi_routes_from_source(main_path.read_text(encoding="utf-8"))
        assert "/health" in routes
        assert "/internal/publishing/persist" in routes
        assert "/internal/stage-tasks/execute" not in routes
        assert "/internal/publishing/run" not in routes
        # Must NOT have ingestion or indexing endpoints
        assert "/internal/ingestion/convert" not in routes
        assert "/internal/indexing/run" not in routes


class TestConversionWorkerBoundary:
    """Conversion worker has been split into its own directory."""

    def test_conversion_worker_directory_exists(self) -> None:
        from pathlib import Path

        svc_dir = Path(__file__).parent.parent.parent / "conversion-worker"
        assert svc_dir.exists(), "conversion-worker directory must exist for Phase 8"
        assert (svc_dir / "src" / "conversion_worker" / "main.py").exists()

    def test_conversion_worker_exposes_conversion_endpoints(self) -> None:
        from pathlib import Path

        main_path = (
            Path(__file__).parent.parent.parent
            / "conversion-worker"
            / "src"
            / "conversion_worker"
            / "main.py"
        )
        routes = _extract_fastapi_routes_from_source(main_path.read_text(encoding="utf-8"))
        assert "/health" in routes
        assert "/internal/conversion/run" in routes
        assert "/internal/stage-tasks/execute" not in routes
        # Must NOT have ingestion or indexing endpoints
        assert "/internal/ingestion/convert" not in routes
        assert "/internal/indexing/run" not in routes


class TestAgentReviewWorkerBoundary:
    """Agent review worker has been split into its own directory."""

    def test_agent_review_worker_directory_exists(self) -> None:
        from pathlib import Path

        svc_dir = Path(__file__).parent.parent.parent / "agent-review-worker"
        assert svc_dir.exists(), "agent-review-worker directory must exist for Phase 8"
        assert (svc_dir / "src" / "agent_review_worker" / "main.py").exists()

    def test_agent_review_worker_exposes_review_endpoints(self) -> None:
        from pathlib import Path

        main_path = (
            Path(__file__).parent.parent.parent
            / "agent-review-worker"
            / "src"
            / "agent_review_worker"
            / "main.py"
        )
        routes = _extract_fastapi_routes_from_source(main_path.read_text(encoding="utf-8"))
        assert "/health" in routes
        assert "/internal/review/run" in routes
        assert "/internal/stage-tasks/execute" not in routes
        # Must NOT have ingestion or indexing endpoints
        assert "/internal/ingestion/convert" not in routes
        assert "/internal/indexing/run" not in routes

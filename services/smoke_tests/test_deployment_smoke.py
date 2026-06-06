"""Deployment-level smoke test — starts real services, uploads a document,
and verifies the full pipeline through actual HTTP calls.

This catches bugs that live at process boundaries: missing env vars,
wrong port numbers, HTTP endpoint errors, outbox race conditions.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import json as _json
import pytest

ROOT = Path(__file__).resolve().parents[2]
EKB_SVC = ROOT / "scripts" / "ekb-svc.py"

# Which services we need for the full pipeline test
REQUIRED_SERVICES = [
    "document-service",
    "ingestion-worker",
    "conversion-worker",
    "agent-review-worker",
    "approval-service",
    "publishing-worker",
    "workbench-api",
    "indexing",
    "admin",
]

HEALTH_URLS: dict[str, str] = {}

# Token for demo-admin (matches the one used by ekb-svc.py smoke mode)
TOKEN = (
    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJkZW1vLWFkbWluIiwiZW1haWwiOiJkZW1vQGV4YW1wbGUuY29tIiwicm9sZXMiOlsia25vd2xlZGdlX2FkbWluIiwidXBsb2FkZXIiLCJyZXZpZXdlciIsImNodW5rX2VkaXRvciJdLCJ0ZW5hbnRfaWQiOiJkZWZhdWx0IiwiYWxsb3dlZF9jb2xsZWN0aW9ucyI6WyIqIl19."
    "VbBjQ1VIoY7weiicGtnrGxi139X0XF6_iVdOjkKVqHo"
)

HEADERS = {"Authorization": TOKEN}


def _url(port: int, path: str = "") -> str:
    return f"http://127.0.0.1:{port}{path}"


def _health_urls() -> dict[str, str]:
    return {
        "document-service": _url(8006, "/health"),
        "ingestion-worker": _url(18088, "/health"),
        "conversion-worker": _url(18089, "/health"),
        "agent-review-worker": _url(18090, "/health"),
        "approval-service": _url(18087, "/health"),
        "publishing-worker": _url(18086, "/health"),
        "workbench-api": _url(18083, "/workbench/health"),
        "indexing": _url(18080, "/health"),
        "admin": _url(18084, "/health"),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Services required for the upload → review pipeline (no access/retrieval).
CORE_SERVICES: dict[str, dict] = {
    "document-service": {
        "port": 8006,
        "health": "/health",
        "cmd": [sys.executable, "-m", "uvicorn", "document_service.main:app",
                "--host", "127.0.0.1", "--port", "8006", "--http", "h11"],
        "cwd": str(ROOT / "services" / "intake-pipeline" / "document-service"),
    },
    "indexing": {
        "port": 18080,
        "health": "/health",
        "cmd": [sys.executable, "-m", "uvicorn", "indexing_service.main:app",
                "--host", "127.0.0.1", "--port", "18080", "--http", "h11"],
        "cwd": str(ROOT / "services" / "indexing"),
    },
    "ingestion-worker": {
        "port": 18088,
        "health": "/health",
        "cmd": [sys.executable, "-m", "uvicorn", "ingestion_worker.main:app",
                "--host", "127.0.0.1", "--port", "18088", "--http", "h11"],
        "cwd": str(ROOT / "services" / "intake-pipeline" / "ingestion-worker"),
    },
    "conversion-worker": {
        "port": 18089,
        "health": "/health",
        "cmd": [sys.executable, "-m", "uvicorn", "conversion_worker.main:app",
                "--host", "127.0.0.1", "--port", "18089", "--http", "h11"],
        "cwd": str(ROOT / "services" / "intake-pipeline" / "conversion-worker"),
    },
    "agent-review-worker": {
        "port": 18090,
        "health": "/health",
        "cmd": [sys.executable, "-m", "uvicorn", "agent_review_worker.main:app",
                "--host", "127.0.0.1", "--port", "18090", "--http", "h11"],
        "cwd": str(ROOT / "services" / "intake-pipeline" / "agent-review-worker"),
    },
    "approval-service": {
        "port": 18087,
        "health": "/health",
        "cmd": [sys.executable, "-m", "uvicorn", "approval_service.main:app",
                "--host", "127.0.0.1", "--port", "18087", "--http", "h11"],
        "cwd": str(ROOT / "services" / "intake-pipeline" / "approval-service"),
    },
    "publishing-worker": {
        "port": 18086,
        "health": "/health",
        "cmd": [sys.executable, "-m", "uvicorn", "publishing_worker.main:app",
                "--host", "127.0.0.1", "--port", "18086", "--http", "h11"],
        "cwd": str(ROOT / "services" / "intake-pipeline" / "publishing-worker"),
    },
    "workbench-api": {
        "port": 18083,
        "health": "/workbench/health",
        "cmd": [sys.executable, "-m", "uvicorn", "workbench_api.main:app",
                "--host", "127.0.0.1", "--port", "18083", "--http", "h11"],
        "cwd": str(ROOT / "services" / "workbench-api"),
    },
    "admin": {
        "port": 18084,
        "health": "/health",
        "cmd": [sys.executable, "-m", "uvicorn", "admin_service.main:app",
                "--host", "127.0.0.1", "--port", "18084", "--http", "h11"],
        "cwd": str(ROOT / "services" / "admin"),
    },
}


def _start_services(timeout: float = 120.0) -> dict[str, subprocess.Popen]:
    """Start each core service as an independent subprocess."""
    procs: dict[str, subprocess.Popen] = {}

    for name, cfg in CORE_SERVICES.items():
        env = os.environ.copy()
        _set_service_env(name, env)
        log_path = ROOT / ".verify" / "runtime" / f"smoke-{name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(str(log_path), "w")
        procs[name] = subprocess.Popen(
            cfg["cmd"],
            cwd=cfg["cwd"],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    # Give services time to start before polling
    time.sleep(15)

    # Check that processes are alive and reachable via curl (bypasses httpx issues)
    deadline = time.time() + timeout
    healthy: set[str] = set()
    while time.time() < deadline:
        for name, cfg in CORE_SERVICES.items():
            if name in healthy:
                continue
            proc = procs.get(name)
            if proc is None or proc.poll() is not None:
                continue  # process crashed
            try:
                result = subprocess.run(
                    ["curl", "-sf", f"http://127.0.0.1:{cfg['port']}{cfg['health']}"],
                    timeout=5.0, capture_output=True,
                )
                if result.returncode == 0:
                    healthy.add(name)
            except Exception:
                pass
        if len(healthy) >= len(CORE_SERVICES):
            return procs
        time.sleep(2)

    missing = set(CORE_SERVICES) - healthy
    _stop_services(procs)
    raise RuntimeError(f"Services did not become healthy: {missing}")


# Base PYTHONPATH shared by all services (matches ekb-svc.py _BASE_PYTHONPATH_DIRS)
_BASE_PYTHONPATH = os.pathsep.join(str(ROOT / p) for p in [
    "packages/contracts/src",
    "packages/persistence/src",
    "packages/documents/src",
    "packages/ragflow_runtime/src",
    "packages/intake_runtime/src",
])

# Extra PYTHONPATH entries per service (in addition to {cwd}/src which is added automatically)
_EXTRA_PYTHONPATH: dict[str, list[str]] = {
    "conversion-worker": ["services/intake-pipeline/src"],
    "agent-review-worker": ["services/intake-pipeline/src"],
    "publishing-worker": ["services/intake-pipeline/src"],
    "ingestion-worker": ["services/intake-pipeline/src"],
    "workbench-api": ["services/admin/src"],
}


def _set_service_env(name: str, env: dict) -> None:
    """Set environment variables for a specific service, matching ekb-svc.py."""
    cfg = CORE_SERVICES[name]

    # PYTHONPATH
    path_dirs = [_BASE_PYTHONPATH, str(ROOT / cfg["cwd"] / "src")]
    for extra in _EXTRA_PYTHONPATH.get(name, []):
        path_dirs.append(str(ROOT / extra))
    env["PYTHONPATH"] = os.pathsep.join(path_dirs)

    # Shared env
    env.setdefault("DATABASE_URL", "postgresql+psycopg2://reality_rag:reality_rag@localhost:5432/reality_rag")
    env.setdefault("JWT_SECRET", "smoke-test-secret")
    env.setdefault("JWT_ALGORITHM", "HS256")
    env.setdefault("AUTH_MODE", "smoke")
    env.setdefault("ALLOW_LOCAL_FALLBACK_FOR_TESTS", "true")

    if name in ("ingestion-worker", "conversion-worker", "agent-review-worker", "publishing-worker"):
        env["INDEXING_SERVICE_URL"] = "http://127.0.0.1:18080"
        env["DOCUMENT_SERVICE_URL"] = "http://127.0.0.1:8006"
    if name == "ingestion-worker":
        env["APPROVAL_SERVICE_URL"] = "http://127.0.0.1:18087"
        env["PUBLISHING_WORKER_URL"] = "http://127.0.0.1:18086"
    if name == "workbench-api":
        env["INTAKE_BASE_URL"] = "http://127.0.0.1:18088"
        env["DOCUMENT_SERVICE_BASE_URL"] = "http://127.0.0.1:8006"
        env["INDEXING_BASE_URL"] = "http://127.0.0.1:18080"
        env["APPROVAL_BASE_URL"] = "http://127.0.0.1:18087"
        env["WORKBENCH_EVENT_KEY_INTAKE"] = "smoke-intake-key"
        env["WORKBENCH_EVENT_KEY_APPROVAL"] = "smoke-approval-key"
        env["WORKBENCH_EVENT_KEY_INDEXING"] = "smoke-indexing-key"


def _stop_services(procs: dict[str, subprocess.Popen]) -> None:
    for name, proc in procs.items():
        try:
            proc.terminate()
        except Exception:
            pass
    for proc in procs.values():
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


def _api_post(path: str, json: dict | None = None, files: dict | None = None) -> dict[str, Any]:
    """POST to workbench API via curl (avoids httpx patching issues)."""
    cmd = ["curl", "-s", "-H", f"Authorization: {HEADERS['Authorization']}"]
    if json:
        cmd += ["-H", "Content-Type: application/json", "-d", _json.dumps(json)]
    if files:
        for field_name, (filename, content, mime) in files.items():
            cmd += ["-F", f"{field_name}=@{filename};type={mime}"]
    cmd.append(_url(18083, path))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"POST {path} failed: {result.stderr}")
    data = _json.loads(result.stdout)
    if isinstance(data, dict) and data.get("detail"):
        raise RuntimeError(f"POST {path} returned error: {data['detail']}")
    return data


def _api_get(path: str) -> dict[str, Any]:
    """GET from workbench API via curl (avoids httpx patching issues)."""
    result = subprocess.run(
        ["curl", "-s", "-H", f"Authorization: {HEADERS['Authorization']}", _url(18083, path)],
        capture_output=True, text=True, timeout=10.0,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"GET {path} failed: {result.stderr}")
    return _json.loads(result.stdout)


def _poll_task(upload_id: str, target_statuses: set[str], timeout: float = 120.0) -> dict:
    """Poll task until it reaches one of the target statuses."""
    deadline = time.time() + timeout
    last_status = ""
    while time.time() < deadline:
        try:
            task = _api_get(f"/workbench/tasks/{upload_id}")
        except Exception:
            time.sleep(1)
            continue
        current = task.get("status", "")
        if current != last_status:
            last_status = current
        if current in target_statuses:
            return task
        time.sleep(2)
    raise AssertionError(
        f"Task {upload_id} did not reach {target_statuses} within {timeout}s, last status: {last_status}"
    )


# ---------------------------------------------------------------------------
# Infrastructure check
# ---------------------------------------------------------------------------

INFRA_PORTS = {
    "PostgreSQL": 5432,
    "OpenSearch": 19201,
    "Qdrant": 6333,
    "Redis": 6379,
}


def _infra_ready() -> bool:
    """Check that all required infrastructure services are reachable."""
    missing = []
    for name, port in INFRA_PORTS.items():
        import socket
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2.0):
                pass
        except Exception:
            missing.append(f"{name} (port {port})")
    return len(missing) == 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def services():
    """Start core services as independent processes.

    Skips if infrastructure (PostgreSQL, OpenSearch, etc.) is not available.
    """
    if not _infra_ready():
        pytest.skip("Infrastructure not available (PostgreSQL, OpenSearch, Qdrant, Redis required)")

    print("\n[smoke] Starting core services...")
    procs = _start_services()
    print(f"[smoke] {len(procs)} services healthy.")
    yield
    print("\n[smoke] Stopping services...")
    _stop_services(procs)
    print("[smoke] Done.")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeploymentSmoke:
    """End-to-end tests against real running services."""

    def test_all_services_healthy(self, services):
        """Every core service responds to its health endpoint."""
        for name, cfg in CORE_SERVICES.items():
            url = f"http://127.0.0.1:{cfg['port']}{cfg['health']}"
            result = subprocess.run(["curl", "-sf", url], capture_output=True, timeout=5.0)
            assert result.returncode == 0, f"{name} at {url} failed: {result.stderr}"

    def test_upload_and_status_progression(self, services):
        """Upload a markdown file and verify status progresses past 'uploading'.

        Does not require the full pipeline to reach 'published' — that depends
        on external services (RAGFlow, OpenSearch, Qdrant) that may not be
        configured in every environment.  Instead verifies the status moves
        beyond 'uploading'/'ready' into 'parsing' or further.
        """
        # 1. Create upload session
        create = _api_post("/workbench/uploads", json={
            "collection_id": "test1",
            "filename": "smoke-test.md",
            "mime_type": "text/markdown",
            "size_bytes": 64,
        })
        upload_id = create["upload_id"]
        assert create["status"] in ("uploading", "failed")

        # 2. Upload file content (use curl with temp file to avoid httpx patches)
        import tempfile
        content = b"# Smoke Test\n\nHello from deployment smoke."
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST",
                 "-H", f"Authorization: {HEADERS['Authorization']}",
                 "-F", f"file=@{tmp_path};type=text/markdown",
                 _url(18083, f"/workbench/uploads/{upload_id}/content")],
                capture_output=True, text=True, timeout=30.0,
            )
        finally:
            Path(tmp_path).unlink()
        assert result.returncode == 0, f"Upload failed: {result.stderr}"
        uploaded = _json.loads(result.stdout)
        assert uploaded.get("source_file_id"), f"No source_file_id in response: {uploaded}"
        assert uploaded["status"] == "ready", f"Expected status=ready, got {uploaded['status']}"

        # 3. Poll task until it leaves 'uploading'/'ready'.
        task = _poll_task(
            upload_id,
            {"parsing", "reviewing", "approved", "rejected", "failed", "publishing", "published", "indexing"},
            timeout=60.0,
        )
        assert task["status"] != "uploading", f"Task stuck at uploading: {task}"
        assert task.get("source_file_id"), "Task missing source_file_id"
        print(f"[smoke] Task {upload_id} → status={task['status']}, "
              f"source_file_state={task.get('source_file_state')}, "
              f"intake_job_state={task.get('intake_job_state')}")

    def test_failed_document_shows_failed_not_uploading(self, services):
        """A failed intake job must show 'failed', not 'uploading' or 'parsing'.

        Regression test for the bug where failed conversions displayed 'uploading'
        because the projection was never updated with the actual job state.
        """
        tasks = _api_get("/workbench/tasks")
        for item in tasks.get("items", []):
            status = item.get("status", "")
            source_state = item.get("source_file_state")
            job_state = item.get("intake_job_state")
            # If the job is actually failed, the status must say so
            if job_state == "failed":
                assert status == "failed", (
                    f"Task {item['upload_id']} ({item['filename']}): "
                    f"intake_job_state=failed but status={status}"
                )
            # If source file is claimed/consumed, status should not be 'uploading'
            if source_state in ("claimed", "consumed", "ready"):
                assert status != "uploading", (
                    f"Task {item['upload_id']} ({item['filename']}): "
                    f"source_file_state={source_state} but status=uploading"
                )
            # If an intake_job_id exists, status should be past 'uploading'
            if item.get("intake_job_id") and item.get("source_file_state"):
                assert status not in ("uploading", "ready"), (
                    f"Task {item['upload_id']} ({item['filename']}): "
                    f"has intake_job_id but status={status}"
                )

    def test_projection_fields_consistent(self, services):
        """Projections with a source_file_id must have an intake_job_id
        if source_file_state indicates the pipeline started.
        """
        tasks = _api_get("/workbench/tasks")
        for item in tasks.get("items", []):
            if item.get("source_file_id") and item.get("source_file_state") in (
                "claimed", "consumed", "cleanable", "cleaned",
            ):
                assert item.get("intake_job_id"), (
                    f"Task {item['upload_id']} ({item['filename']}): "
                    f"source_file_state={item['source_file_state']} but intake_job_id is null"
                )

    def test_no_stuck_uploading_with_source_file(self, services):
        """Any task with a source_file_id must have progressed past 'uploading'."""
        tasks = _api_get("/workbench/tasks")
        stuck = []
        for item in tasks.get("items", []):
            if item.get("source_file_id") and item.get("status") == "uploading":
                stuck.append(f"{item['upload_id']} ({item['filename']})")
        assert not stuck, f"Tasks stuck at 'uploading' despite having source_file_id: {stuck}"

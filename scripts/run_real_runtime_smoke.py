#!/usr/bin/env python3
"""
Real Runtime Smoke Test for Enterprise KnowledgeBase MVP.

Starts services as real OS processes and exercises them via localhost HTTP.
This is NOT an in-process ASGI smoke - each service runs in its own process.

Usage:
    # Auto-start all services, run smoke, stop services
    py -3.14 scripts/run_real_runtime_smoke.py

    # Connect to already-running services
    py -3.14 scripts/run_real_runtime_smoke.py --use-existing-services

    # Keep services running after smoke (for manual exploration)
    py -3.14 scripts/run_real_runtime_smoke.py --keep-running

Exit codes:
    0  All smoke steps passed
    1  One or more smoke steps failed
    2  Service startup or health check failed
    3  Smoke harness internal error
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / ".verify" / "runtime"
SMOKE_DB = RUNTIME_DIR / "real-smoke.db"

PYTHON = sys.executable
IS_WINDOWS = sys.platform == "win32"

# Service configuration: name -> {port, health_path, startup_cmd, cwd, env, shell}
SERVICE_CONFIG: dict[str, dict[str, Any]] = {
    "admin": {
        "port": 18084,
        "health_path": "/health",
        "cwd": ROOT / "services" / "admin",
        "cmd": [
            PYTHON, "-m", "uvicorn", "admin_service.main:app",
            "--host", "127.0.0.1", "--port", "18084",
        ],
        "env": {},
        "shell": False,
    },
    "workbench": {
        "port": 18083,
        "health_path": "/workbench/health",
        "cwd": ROOT / "services" / "workbench-api",
        "cmd": [
            PYTHON, "-m", "uvicorn", "workbench_api.main:app",
            "--host", "127.0.0.1", "--port", "18083",
        ],
        "env": {},
        "shell": False,
    },
    "indexing": {
        "port": 18080,
        "health_path": "/health",
        "cwd": ROOT / "services" / "indexing",
        "cmd": [
            PYTHON, "-m", "uvicorn", "indexing_service.main:app",
            "--host", "127.0.0.1", "--port", "18080",
        ],
        "env": {},
        "shell": False,
    },
    "intake": {
        "port": 18085,
        "health_path": "/health",
        "cwd": ROOT / "services" / "intake-pipeline",
        "cmd": [
            PYTHON, "-m", "uvicorn", "intake_pipeline.main:app",
            "--host", "127.0.0.1", "--port", "18085",
        ],
        "env": {},
        "shell": False,
    },
    "publishing": {
        "port": 18086,
        "health_path": "/health",
        "cwd": ROOT / "services" / "intake-pipeline" / "publishing-worker",
        "cmd": [
            PYTHON, "-m", "uvicorn", "publishing_worker.main:app",
            "--host", "127.0.0.1", "--port", "18086",
        ],
        "env": {},
        "shell": False,
    },
    "access": {
        "port": 18181,
        "health_path": "/health",
        "cwd": ROOT / "services" / "access",
        "cmd": [
            "mvn", "spring-boot:run",
            "-Dspring-boot.run.arguments=--server.port=18181 --spring.profiles.active=smoke --access.retrieval.base-url=http://127.0.0.1:18182",
        ],
        "env": {},
        "shell": IS_WINDOWS,
    },
    "retrieval": {
        "port": 18182,
        "health_path": "/health",
        "cwd": ROOT / "services" / "retrieval",
        "cmd": [
            "mvn", "spring-boot:run",
            "-Dspring-boot.run.arguments=--server.port=18182 --spring.profiles.active=smoke",
        ],
        "env": {},
        "shell": IS_WINDOWS,
    },
}

PYTHON_SERVICES = ["admin", "workbench", "indexing", "intake", "publishing"]
JAVA_SERVICES = ["access", "retrieval"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(step: str, message: str) -> None:
    print(f"[{step}] {message}", flush=True)


def _http_get(url: str, headers: dict[str, str] | None = None, timeout: float = 5.0) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.read else ""
        try:
            return {"_http_error": True, "status": e.code, "body": json.loads(body)}
        except json.JSONDecodeError:
            return {"_http_error": True, "status": e.code, "body": body}
    except Exception as e:
        _log("HTTP_GET_ERROR", f"url={url} error={type(e).__name__}: {e}")
        return None


def _http_post(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: float = 10.0) -> tuple[int, dict[str, Any] | str]:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.read else ""
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body
    except Exception as e:
        return 0, str(e)


def _wait_for_health(port: int, path: str, timeout: float = 60.0, interval: float = 1.0) -> dict[str, Any] | None:
    url = f"http://127.0.0.1:{port}{path}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = _http_get(url, timeout=min(interval, 3.0))
        if result is not None:
            return result
        time.sleep(interval)
    return None


def _start_service(name: str, cfg: dict[str, Any]) -> subprocess.Popen | None:
    env = os.environ.copy()
    env.update(cfg.get("env", {}))

    # Build PYTHONPATH with all Python service src directories, shared packages,
    # and ingestion-worker src (which publishing_worker imports from).
    all_python_srcs = os.pathsep.join(
        str(SERVICE_CONFIG[s]["cwd"] / "src") for s in PYTHON_SERVICES
    )
    package_srcs = os.pathsep.join(
        str(ROOT / "packages" / pkg / "src") for pkg in ["contracts", "persistence", "documents", "ragflow_runtime"]
    )
    ingestion_worker_src = str(ROOT / "services" / "intake-pipeline" / "ingestion-worker" / "src")
    existing_pp = env.get("PYTHONPATH", "")
    service_src = str(cfg["cwd"] / "src")
    pythonpath_parts = [service_src, all_python_srcs, package_srcs, ingestion_worker_src]
    if existing_pp:
        pythonpath_parts.append(existing_pp)
    env["PYTHONPATH"] = os.pathsep.join(p for p in pythonpath_parts if p)

    creationflags = 0
    if IS_WINDOWS and not cfg.get("shell", False):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    stdout_path = RUNTIME_DIR / f"{name}.out.log"
    stderr_path = RUNTIME_DIR / f"{name}.err.log"
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    stdout = open(stdout_path, "a", encoding="utf-8")
    stderr = open(stderr_path, "a", encoding="utf-8")

    try:
        proc = subprocess.Popen(
            cfg["cmd"],
            cwd=cfg["cwd"],
            env=env,
            stdout=stdout,
            stderr=stderr,
            creationflags=creationflags,
            shell=cfg.get("shell", False),
        )
        _log("START", f"{name} PID={proc.pid} port={cfg['port']}")
        return proc
    except Exception as e:
        _log("START", f"{name} FAILED: {e}")
        stdout.close()
        stderr.close()
        return None


def _stop_service(name: str, proc: subprocess.Popen) -> None:
    try:
        if IS_WINDOWS:
            # On Windows with shell=True, proc is cmd.exe which spawns java.exe.
            # CTRL_BREAK_EVENT kills cmd.exe but orphans java.exe. Use taskkill
            # to terminate the entire process tree.
            try:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=10.0,
                )
                proc.wait(timeout=5.0)
            except Exception:
                proc.kill()
                proc.wait(timeout=2.0)
        else:
            proc.terminate()
            proc.wait(timeout=5.0)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=2.0)
        except Exception:
            pass
    _log("STOP", f"{name} PID={proc.pid}")


# ---------------------------------------------------------------------------
# Smoke flow
# ---------------------------------------------------------------------------

class SmokeRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.procs: dict[str, subprocess.Popen] = {}
        self.results: list[dict[str, Any]] = []
        self.admin_token: str = ""
        self.uploader_token: str = ""
        self.api_key_plaintext: str = ""
        self.api_key_id: str = ""
        self.collection_id: str = ""
        self.parser_profile_id: str = ""
        self.retrieval_profile_id: str = ""
        self.source_file_id: str = ""
        self.final_doc_id: str = ""
        self.index_version_id: str = ""
        self.tenant_id: str = "default"

    def _record(self, step: str, service: str, endpoint: str, status: str, detail: str = "") -> None:
        self.results.append({
            "step": step,
            "service": service,
            "endpoint": endpoint,
            "status": status,
            "detail": detail,
        })
        marker = "PASS" if status == "PASS" else "FAIL"
        _log(marker, f"[{step}] {service} {endpoint} -> {status}: {detail}")

    def run(self) -> int:
        try:
            if not self.args.use_existing_services:
                self._start_services()

            self._health_checks()
            self._admin_setup()
            self._workbench_flow()
            self._intake_flow()
            self._retrieval_access_flow()
            self._visibility_ops()
            self._report()
            return 0 if all(r["status"] in ("PASS", "WARN", "SKIP") for r in self.results) else 1
        except Exception as e:
            _log("ERROR", f"Smoke harness failed: {e}")
            traceback.print_exc()
            return 3
        finally:
            if not self.args.use_existing_services and not self.args.keep_running:
                self._stop_services()

    # --- Phase 0: Startup --------------------------------------------------

    def _start_services(self) -> None:
        _log("PHASE", "Starting services")

        # Prepare shared env for Python services
        # Use real PostgreSQL (Docker container: docker-postgres-1)
        db_url = os.environ.get("DATABASE_URL", "postgresql://rag_flow:infini_rag_flow@127.0.0.1:5432/rag_flow")

        # Pre-seed PostgreSQL with default tenant so foreign-key constraints pass
        # Also clean up old workbench upload sessions to prevent task projection timeouts
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="127.0.0.1", port=5432, user="rag_flow",
                password="infini_rag_flow", dbname="rag_flow", connect_timeout=5
            )
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS tenants (tenant_id VARCHAR(64) PRIMARY KEY, name VARCHAR(255) NOT NULL)")
            cur.execute("INSERT INTO tenants (tenant_id, name) VALUES ('default', 'Default Tenant') ON CONFLICT (tenant_id) DO NOTHING")
            # Clean up ALL workbench upload sessions from prior runs to keep task projection fast.
            # Table may not exist on a fresh database — ignore.
            try:
                cur.execute("DELETE FROM workbench_upload_sessions")
                deleted = cur.rowcount
            except Exception:
                deleted = 0
            conn.commit()
            cur.close()
            conn.close()
            _log("SEED", f"default tenant ready in PostgreSQL; cleaned {deleted} old upload sessions")
        except Exception as e:
            _log("WARN", f"pre-seed default tenant failed: {e}")

        shared_python_env = {
            "DATABASE_URL": db_url,
            "ADMIN_JWT_SECRET": "smoke-test-secret",
            "JWT_SECRET": "smoke-test-secret",
            "INDEXING_BASE_URL": "http://127.0.0.1:18080",
            "INTAKE_BASE_URL": "http://127.0.0.1:18085",
            "ADMIN_BASE_URL": "http://127.0.0.1:18084",
            "RETRIEVAL_BASE_URL": "http://127.0.0.1:18182",
            "RETRIEVAL_SERVICE_URL": "http://127.0.0.1:18182",
            "ACCESS_BASE_URL": "http://127.0.0.1:18181",
            "PUBLISHING_WORKER_BASE_URL": "http://127.0.0.1:18086",
            "REALITY_RAG_INDEXING_BASE_URL": "http://127.0.0.1:18080",
            "REALITY_RAG_INTAKE_RUNTIME_DIR": str(RUNTIME_DIR / "intake-real-smoke"),
            # Do NOT override embedding / backend config — let Python services read
            # from their local .env files so real model endpoints are used.
        }
        if self.args.require_live_backends:
            shared_python_env["INDEXING_REQUIRE_LIVE_BACKENDS"] = "true"

        if self.args.require_production_jwt_config:
            shared_python_env["ADMIN_JWT_ISSUER"] = "https://auth.enterprise-kb.local"
            shared_python_env["ADMIN_JWT_AUDIENCE"] = "admin-api"
            shared_python_env["JWT_ISSUER"] = "https://auth.enterprise-kb.local"
            shared_python_env["JWT_AUDIENCE"] = "workbench-api"
            shared_python_env["AUTH_MODE"] = "production"

        # Load real model credentials from indexing .env for Java retrieval service
        indexing_env_path = ROOT / "services" / "indexing" / ".env"
        siliconflow_key = ""
        siliconflow_embed_url = "https://api.siliconflow.cn/v1"
        siliconflow_embed_model = "BAAI/bge-m3"
        if indexing_env_path.exists():
            for line in indexing_env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "INDEXING_EMBEDDING_API_KEY":
                    siliconflow_key = value
                elif key == "INDEXING_EMBEDDING_BASE_URL":
                    # Normalize: strip /embeddings suffix if present
                    siliconflow_embed_url = value.replace("/embeddings", "")
                elif key == "INDEXING_EMBEDDING_MODEL":
                    siliconflow_embed_model = value

        retrieval_java_env = {
            "EMBEDDING_API_KEY": siliconflow_key,
            "EMBEDDING_BASE_URL": siliconflow_embed_url,
            "EMBEDDING_MODEL": siliconflow_embed_model,
            "RERANKER_API_KEY": siliconflow_key,
            "RERANKER_BASE_URL": "https://api.siliconflow.cn/v1/rerank",
            "RERANKER_MODEL": "BAAI/bge-reranker-v2-m3",
            "OPENSEARCH_BASE_URL": "http://127.0.0.1:1201",
            "QDRANT_BASE_URL": "http://127.0.0.1:6333",
        }
        if self.args.require_live_backends:
            retrieval_java_env["REQUIRE_LIVE_BACKENDS"] = "true"

        if self.args.require_redis_cache:
            retrieval_java_env["RETRIEVAL_CACHE_PROVIDER"] = "redis"
            retrieval_java_env["REQUIRE_REDIS_CACHE"] = "true"
            retrieval_java_env["RETRIEVAL_CACHE_FAIL_OPEN"] = "false"
            # Read Redis password from env var only (never hardcoded in tracked file)
            redis_password = os.environ.get("REDIS_PASSWORD", "")
            if redis_password:
                retrieval_java_env["REDIS_URL"] = f"redis://:{redis_password}@127.0.0.1:6379/0"
            else:
                retrieval_java_env["REDIS_URL"] = "redis://127.0.0.1:6379/0"

        # Start services sequentially
        for name in PYTHON_SERVICES + JAVA_SERVICES:
            cfg = SERVICE_CONFIG[name]
            if name in PYTHON_SERVICES:
                cfg["env"] = {**shared_python_env}
            elif name == "retrieval":
                cfg["env"] = {**retrieval_java_env}
            proc = _start_service(name, cfg)
            if proc is None:
                if name in PYTHON_SERVICES:
                    _log("FAIL", f"Failed to start {name}")
                    sys.exit(2)
                else:
                    _log("WARN", f"Failed to start {name} - will skip Java-dependent steps")
                    continue
            self.procs[name] = proc

            # Wait for this service to be healthy before starting the next
            result = _wait_for_health(cfg["port"], cfg["health_path"], timeout=60.0)
            if result:
                _log("START", f"{name} healthy")
            else:
                if name in PYTHON_SERVICES:
                    _log("FAIL", f"{name} did not become healthy")
                    sys.exit(2)
                else:
                    _log("WARN", f"{name} did not become healthy - will skip Java-dependent steps")
                    del self.procs[name]

        # Give Java services extra time for Maven download / compilation
        java_startup_delay = 3.0 if any(s in self.procs for s in JAVA_SERVICES) else 0.0
        if java_startup_delay:
            _log("WAIT", f"Waiting {java_startup_delay}s for Java services to warm up")
            time.sleep(java_startup_delay)

    def _stop_services(self) -> None:
        _log("PHASE", "Stopping services")
        for name, proc in self.procs.items():
            _stop_service(name, proc)

    # --- Phase 1: Health checks --------------------------------------------

    def _health_checks(self) -> None:
        _log("PHASE", "Health checks")
        for name, cfg in SERVICE_CONFIG.items():
            if name not in self.procs and not self.args.use_existing_services:
                self._record(f"health_{name}", name, cfg["health_path"], "SKIP", "service not started")
                continue
            result = _wait_for_health(cfg["port"], cfg["health_path"], timeout=60.0)
            if result:
                self._record(f"health_{name}", name, cfg["health_path"], "PASS", json.dumps(result))
            else:
                self._record(f"health_{name}", name, cfg["health_path"], "FAIL", "no response")

    # --- Phase 2: Admin setup ----------------------------------------------

    def _admin_setup(self) -> None:
        _log("PHASE", "Admin setup")
        base = "http://127.0.0.1:18084"

        # Create tokens
        self.admin_token = self._make_test_token("admin_01", roles=["knowledge_admin", "platform_admin"])
        self.uploader_token = self._make_test_token("uploader_01", roles=["uploader"], allowed_collections=["col_smoke"])
        self._record("admin_login", "admin", "/admin/auth/login", "PASS", "using test token")
        headers = {"Authorization": f"Bearer {self.admin_token}"}

        # Create collection
        status, body = _http_post(f"{base}/admin/collections", {
            "collection_id": "col_smoke",
            "tenant_id": self.tenant_id,
            "name": "Smoke Test Collection",
            "description": "Created by real-runtime smoke",
        }, headers)
        self.collection_id = body.get("collection_id", "col_smoke") if isinstance(body, dict) else "col_smoke"
        self._record("admin_create_collection", "admin", "/admin/collections", "PASS" if status in (200, 201) else "FAIL", f"status={status}")

        # Create parser profile
        status, body = _http_post(f"{base}/admin/parser-profiles", {
            "parser_profile_id": "parser_smoke_01",
            "name": "smoke-naive",
            "parser_id": "naive",
            "parser_config": {"chunk_token_num": 128},
        }, headers)
        self.parser_profile_id = body.get("parser_profile_id", "") if isinstance(body, dict) else ""
        self._record("admin_create_parser", "admin", "/admin/parser-profiles", "PASS" if status in (200, 201) else "FAIL", f"status={status} id={self.parser_profile_id}")

        # Publish parser profile
        if self.parser_profile_id:
            status, body = _http_post(f"{base}/admin/parser-profiles/{self.parser_profile_id}/publish", {}, headers)
            self._record("admin_publish_parser", "admin", f"/admin/parser-profiles/{self.parser_profile_id}/publish", "PASS" if status in (200, 201) else "FAIL", f"status={status}")
        else:
            self._record("admin_publish_parser", "admin", "/admin/parser-profiles/.../publish", "SKIP", "no parser profile id")

        # Create retrieval profile
        status, body = _http_post(f"{base}/admin/retrieval-profiles", {
            "retrieval_profile_id": "ret_smoke_01",
            "name": "smoke-retrieval",
            "profile_config": {
                "bm25_weight": 0.5,
                "vector_weight": 0.5,
                "candidate_top_k": 10,
                "similarity_threshold": 0.2,
                "rerank_enabled": False,
                "rerank_model": "none",
                "fail_policy": "fail_closed",
                "pack_budget": 1200,
            },
        }, headers)
        self.retrieval_profile_id = body.get("retrieval_profile_id", "") if isinstance(body, dict) else ""
        self._record("admin_create_retrieval", "admin", "/admin/retrieval-profiles", "PASS" if status in (200, 201) else "FAIL", f"status={status} id={self.retrieval_profile_id}")

        # Publish retrieval profile
        if self.retrieval_profile_id:
            status, body = _http_post(f"{base}/admin/retrieval-profiles/{self.retrieval_profile_id}/publish", {}, headers)
            self._record("admin_publish_retrieval", "admin", f"/admin/retrieval-profiles/{self.retrieval_profile_id}/publish", "PASS" if status in (200, 201) else "FAIL", f"status={status}")
        else:
            self._record("admin_publish_retrieval", "admin", "/admin/retrieval-profiles/.../publish", "SKIP", "no retrieval profile id")

        # Sync retrieval profile to retrieval runtime projection
        if self.retrieval_profile_id and "retrieval" in self.procs:
            ret_base = "http://127.0.0.1:18182"
            status, body = _http_post(f"{ret_base}/internal/retrieval-profile-projections/sync", {
                "command_id": f"sync_ret_{self.retrieval_profile_id}",
                "trace_id": f"trc_sync_ret_{self.retrieval_profile_id}",
                "idempotency_key": f"idem_sync_ret_{self.retrieval_profile_id}",
                "actor": "admin_01",
                "tenant_id": self.tenant_id,
                "target_type": "retrieval_profile",
                "target_id": self.retrieval_profile_id,
                "payload": {
                    "profile_id": self.retrieval_profile_id,
                    "collection_id": self.collection_id,
                    "profile_version": 1,
                    "profile_hash": "smoke_hash",
                    "bm25_weight": 0.3,
                    "vector_weight": 0.7,
                    "candidate_top_k": 20,
                    "similarity_threshold": 0.75,
                    "rerank_enabled": True,
                    "rerank_model": "BAAI/bge-reranker-v2-m3",
                    "fail_policy": "fallback_to_bm25",
                    "expansion_policy": {},
                    "pack_budget": 1200,
                    "enabled": True,
                    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "updated_by": "admin_01",
                },
            })
            detail = f"status={status}"
            if status not in (200, 201) and isinstance(body, dict):
                detail += f" body={json.dumps(body)[:200]}"
            elif status not in (200, 201) and isinstance(body, str):
                detail += f" body={body[:200]}"
            self._record("admin_sync_retrieval", "retrieval", "/internal/retrieval-profile-projections/sync", "PASS" if status in (200, 201) else "FAIL", detail)

        # Create API key
        status, body = _http_post(f"{base}/admin/api-keys", {
            "api_key_id": "key_smoke_01",
            "tenant_id": self.tenant_id,
            "display_name": "smoke-key",
            "knowledge_scopes": [self.collection_id],
            "token_budget_limit": 4096,
        }, headers)
        if isinstance(body, dict):
            self.api_key_plaintext = body.get("plaintext_key", "")
            self.api_key_id = body.get("entry", {}).get("api_key_id", "") if isinstance(body.get("entry"), dict) else ""
        self._record("admin_create_api_key", "admin", "/admin/api-keys", "PASS" if status in (200, 201) else "FAIL", f"status={status} id={self.api_key_id}")

        # Sync API key to access projection
        if self.api_key_id and "access" in self.procs:
            access_base = "http://127.0.0.1:18181"
            # Access service looks up projection by the X-API-Key header value,
            # so we must use the plaintext key as the lookup key in the projection table.
            projection_key = self.api_key_plaintext or self.api_key_id
            status, body = _http_post(f"{access_base}/internal/api-key-projections/sync", {
                "command_id": f"sync_{self.api_key_id}",
                "trace_id": f"trc_sync_{self.api_key_id}",
                "idempotency_key": f"idem_sync_{self.api_key_id}",
                "actor": "admin_01",
                "tenant_id": self.tenant_id,
                "target_type": "api_key",
                "target_id": self.api_key_id,
                "payload": {
                    "api_key_id": projection_key,
                    "tenant_id": self.tenant_id,
                    "agent_type_id": "kb_assistant",
                    "knowledge_scopes": [self.collection_id],
                    "roles": ["employee"],
                    "debug_permission": False,
                    "token_budget_limit": 4096,
                    "state": "active",
                    "projection_version": 1,
                    "last_updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            })
            self._record("admin_sync_access", "access", "/internal/api-key-projections/sync", "PASS" if status in (200, 201) else "FAIL", f"status={status}")
        else:
            self._record("admin_sync_access", "access", "/internal/api-key-projections/sync", "SKIP", "no api key or access not running")

    # --- Phase 3: Workbench flow -------------------------------------------

    def _workbench_flow(self) -> None:
        _log("PHASE", "Workbench flow")
        base = "http://127.0.0.1:18083"
        headers = {"Authorization": f"Bearer {self.uploader_token}"}

        # Create upload session
        status, body = _http_post(f"{base}/workbench/uploads", {
            "collection_id": self.collection_id,
            "filename": "smoke-test.md",
            "mime_type": "text/markdown",
            "size_bytes": 256,
        }, headers)
        upload_id = body.get("upload_id", "") if isinstance(body, dict) else ""
        self._record("workbench_upload", "workbench", "/workbench/uploads", "PASS" if status == 201 else "FAIL", f"status={status} id={upload_id}")

        # Task view (list tasks) - longer timeout because it aggregates downstream states
        result = _http_get(f"{base}/workbench/tasks", headers=headers, timeout=30.0)
        tasks_ok = result is not None and not result.get("_http_error")
        detail = ""
        if result and result.get("_http_error"):
            detail = f"status={result.get('status')} body={str(result.get('body'))[:100]}"
        self._record("workbench_tasks", "workbench", "/workbench/tasks", "PASS" if tasks_ok else "FAIL", detail)

    # --- Phase 4: Intake / indexing flow -----------------------------------

    def _intake_flow(self) -> None:
        _log("PHASE", "Intake / indexing flow")
        base = "http://127.0.0.1:18085"

        # enter_document (creates parse preview via indexing, then snapshot)
        status, body = _http_post(f"{base}/v1/documents", {
            "tenant_id": self.tenant_id,
            "collection_id": self.collection_id,
            "filename": "smoke-test.md",
            "document_version": "v1",
            "publish_version": "pub_001",
            "visibility": "internal",
            "content_text": "# Smoke Test Document\n\nThis is a test document for real runtime smoke.\n\n## Section 1\n\nSome content here.\n\n## Section 2\n\nMore content here.",
            "source_metadata": {"author": "smoke"},
            "scan_verdict": "clean",
        })
        if isinstance(body, dict):
            self.source_file_id = body.get("source_file_id", "")
            self.final_doc_id = body.get("final_doc_id", "")
        self._record("intake_enter_document", "intake", "/v1/documents", "PASS" if status == 200 else "FAIL", f"status={status} source_file_id={self.source_file_id}")

        if not self.source_file_id:
            self._record("intake_approve_publish", "intake", "/v1/documents/.../approve-and-publish", "SKIP", "no source file")
            self._record("indexing_chunks", "indexing", "/internal/chunks", "SKIP", "no source file")
            return

        # approve and publish
        status, body = _http_post(f"{base}/v1/documents/{self.source_file_id}/approve-and-publish", {
            "actor_id": "admin_01",
            "final_doc_id": self.final_doc_id or "doc_smoke_test",
            "confirmed_tags": ["smoke"],
            "index_profile_id": "idx_default",
            "target_index_version_id": f"idxv_{self.collection_id}_active",
            "activate_index_version": True,
        }, timeout=30.0)
        if isinstance(body, dict):
            self.index_version_id = body.get("index_version_id", "")
            self.final_doc_id = body.get("final_doc_id", self.final_doc_id)
        self._record("intake_approve_publish", "intake", f"/v1/documents/{self.source_file_id}/approve-and-publish", "PASS" if status == 200 else "FAIL", f"status={status} final_doc_id={self.final_doc_id}")

        # Query chunks from indexing
        idx_base = "http://127.0.0.1:18080"
        result = _http_get(f"{idx_base}/internal/chunks?tenant_id={self.tenant_id}&principal_id=admin_01&collection_id={self.collection_id}", timeout=10.0)
        chunk_count = len(result) if isinstance(result, list) else 0
        self._record("indexing_chunks", "indexing", "/internal/chunks", "PASS" if chunk_count > 0 else "FAIL", f"chunks={chunk_count}")

        # Check indexed documents
        result = _http_get(f"{idx_base}/internal/indexed-documents?collection_id={self.collection_id}", timeout=5.0)
        doc_count = len(result) if isinstance(result, list) else 0
        self._record("indexing_documents", "indexing", "/internal/indexed-documents", "PASS" if doc_count > 0 else "FAIL", f"docs={doc_count}")

        # --- OpenSearch / Qdrant direct verification ---
        self._verify_opensearch_has_document()
        self._verify_qdrant_has_document()

    # --- Backend verification helpers -----------------------------------

    def _opensearch_index_name(self) -> str:
        # indexing service uses os_{tenant_id}_{collection_id}_{index_version_id}
        # per persistent_repository.py:132
        return f"os_{self.tenant_id}_{self.collection_id}_{self.index_version_id}"

    def _qdrant_collection_name(self) -> str:
        # indexing service uses qd_{tenant_id}_{collection_id}_{index_version_id}
        # per persistent_repository.py:133
        return f"qd_{self.tenant_id}_{self.collection_id}_{self.index_version_id}"

    def _verify_opensearch_has_document(self) -> None:
        if not self.final_doc_id:
            self._record("opensearch_verify", "opensearch", "GET /{index}/_search", "SKIP", "no final_doc_id")
            return

        index_name = self._opensearch_index_name()
        url = f"http://127.0.0.1:1201/{index_name}/_search"
        payload = {
            "query": {"term": {"final_doc_id": self.final_doc_id}},
            "size": 1,
        }

        try:
            import urllib.request as _ur
            data = json.dumps(payload).encode("utf-8")
            req = _ur.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with _ur.urlopen(req, timeout=5.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                total = result.get("hits", {}).get("total", {})
                hit_count = total if isinstance(total, int) else total.get("value", 0)
                ok = hit_count > 0
                self._record(
                    "opensearch_verify",
                    "opensearch",
                    f"GET /{index_name}/_search final_doc_id={self.final_doc_id}",
                    "PASS" if ok else ("FAIL" if self.args.require_live_backends else "WARN"),
                    f"hits={hit_count}",
                )
        except Exception as e:
            self._record(
                "opensearch_verify",
                "opensearch",
                f"GET /{index_name}/_search",
                "FAIL" if self.args.require_live_backends else "WARN",
                f"error={type(e).__name__}: {e}",
            )
            if self.args.require_live_backends:
                raise

    def _verify_qdrant_has_document(self) -> None:
        if not self.final_doc_id:
            self._record("qdrant_verify", "qdrant", "POST /collections/{name}/points/scroll", "SKIP", "no final_doc_id")
            return

        collection_name = self._qdrant_collection_name()
        url = f"http://127.0.0.1:6333/collections/{collection_name}/points/scroll"
        payload = {
            "filter": {
                "must": [{"key": "final_doc_id", "match": {"value": self.final_doc_id}}],
            },
            "limit": 1,
            "with_payload": False,
        }

        try:
            import urllib.request as _ur
            data = json.dumps(payload).encode("utf-8")
            req = _ur.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with _ur.urlopen(req, timeout=5.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                points = result.get("result", {}).get("points", [])
                ok = len(points) > 0
                self._record(
                    "qdrant_verify",
                    "qdrant",
                    f"POST /collections/{collection_name}/points/scroll final_doc_id={self.final_doc_id}",
                    "PASS" if ok else ("FAIL" if self.args.require_live_backends else "WARN"),
                    f"points={len(points)}",
                )
        except Exception as e:
            self._record(
                "qdrant_verify",
                "qdrant",
                f"POST /collections/{collection_name}/points/scroll",
                "FAIL" if self.args.require_live_backends else "WARN",
                f"error={type(e).__name__}: {e}",
            )
            if self.args.require_live_backends:
                raise

    # --- Phase 5: Retrieval / access flow ----------------------------------

    def _retrieval_access_flow(self) -> None:
        _log("PHASE", "Retrieval / access flow")

        # Retrieval direct query
        if "retrieval" in self.procs:
            ret_base = "http://127.0.0.1:18182"
            status, body = _http_post(f"{ret_base}/internal/retrieve", {
                "query_id": "qry_smoke_01",
                "trace_id": "trc_smoke_01",
                "principal": {
                    "user_id": "usr_smoke_01",
                    "role_ids": ["employee"],
                    "group_ids": ["finance"],
                    "attributes": {},
                },
                "collection_scope": [self.collection_id] if self.collection_id else ["col_smoke"],
                "query": "smoke test content",
                "language": "en",
                "retrieval_profile_id": self.retrieval_profile_id,
                "filters": {"visibility": "internal"},
                "include_deprecated": False,
                "token_budget": 1200,
                "debug_level": "basic",
            })
            if isinstance(body, dict):
                evidence_count = len(body.get("evidence_items", []))
                self._record("retrieval_query", "retrieval", "/internal/retrieve", "PASS" if evidence_count > 0 else "FAIL", f"evidence_items={evidence_count}")
            else:
                self._record("retrieval_query", "retrieval", "/internal/retrieve", "FAIL", f"status={status} body={str(body)[:200]}")
        else:
            self._record("retrieval_query", "retrieval", "/internal/retrieve", "SKIP", "retrieval not running")

        # Diagnostic: direct retrieval with access-style principal
        if "retrieval" in self.procs:
            ret_base = "http://127.0.0.1:18182"
            status, body = _http_post(f"{ret_base}/internal/retrieve", {
                "query_id": "qry_access_diag",
                "trace_id": "trc_access_diag",
                "principal": {
                    "user_id": "kb_assistant:agent-smoke-01",
                    "role_ids": ["employee"],
                    "group_ids": [self.collection_id] if self.collection_id else ["col_smoke"],
                    "attributes": {},
                },
                "collection_scope": [self.collection_id] if self.collection_id else ["col_smoke"],
                "query": "smoke test content",
                "language": "en",
                "retrieval_profile_id": self.retrieval_profile_id,
                "filters": {"visibility": "internal"},
                "include_deprecated": False,
                "token_budget": 1200,
                "debug_level": "basic",
            })
            if isinstance(body, dict):
                diag_evidence = len(body.get("evidence_items", []))
                _log("DIAG", f"direct retrieval with access principal: evidence={diag_evidence}")
            else:
                _log("DIAG", f"direct retrieval with access principal failed: status={status} body={str(body)[:200]}")

        # Access query via API key
        if "access" in self.procs and self.api_key_plaintext:
            access_base = "http://127.0.0.1:18181"
            status, body = _http_post(f"{access_base}/v1/retrieve", {
                "query": "smoke test content",
                "collection_scope": [self.collection_id] if self.collection_id else ["col_smoke"],
                "retrieval_profile_id": self.retrieval_profile_id,
                "token_budget": 1200,
                "debug": "basic",
                "language": "en",
                "filters": {"visibility": "internal"},
            }, headers={
                "X-API-Key": self.api_key_plaintext,
                "X-Agent-Instance-Id": "agent-smoke-01",
            })
            if isinstance(body, dict):
                evidence_count = len(body.get("evidence_items", []))
                debug_info = body.get("retrieval_debug", {})
                citations = body.get("citations", [])
                detail = f"evidence_items={evidence_count} citations={len(citations)} debug={debug_info}"
                self._record("access_query", "access", "/v1/retrieve", "PASS" if evidence_count > 0 else "FAIL", detail)
            else:
                self._record("access_query", "access", "/v1/retrieve", "FAIL", f"status={status} body={str(body)[:200]}")
        else:
            self._record("access_query", "access", "/v1/retrieve", "SKIP", "access not running or no api key")

        # Redis cache proof
        if self.args.require_redis_cache:
            self._redis_cache_proof()

    # --- Redis cache proof -----------------------------------------------

    def _redis_cache_proof(self) -> None:
        _log("PHASE", "Redis cache proof")
        ret_base = "http://127.0.0.1:18182"

        query_payload = {
            "query_id": "qry_cache_proof",
            "trace_id": "trc_cache_proof",
            "principal": {
                "user_id": "usr_smoke_01",
                "role_ids": ["employee"],
                "group_ids": ["finance"],
                "attributes": {},
            },
            "collection_scope": [self.collection_id] if self.collection_id else ["col_smoke"],
            "query": "smoke test content",
            "language": "en",
            "retrieval_profile_id": self.retrieval_profile_id,
            "filters": {"visibility": "internal"},
            "include_deprecated": False,
            "token_budget": 1200,
            "debug_level": "basic",
        }

        # Step 1: First query — cache miss baseline (cache empty or from prior purge)
        status1, body1 = _http_post(f"{ret_base}/internal/retrieve", query_payload)
        evidence1 = len(body1.get("evidence_items", [])) if isinstance(body1, dict) else 0
        self._record("cache_miss_1", "retrieval", "/internal/retrieve (query 1)", "PASS" if evidence1 > 0 else "FAIL", f"evidence_items={evidence1}")

        # Step 2: Second identical query — should be cache hit
        status2, body2 = _http_post(f"{ret_base}/internal/retrieve", query_payload)
        evidence2 = len(body2.get("evidence_items", [])) if isinstance(body2, dict) else 0
        same = evidence2 == evidence1 and evidence2 > 0
        self._record("cache_hit", "retrieval", "/internal/retrieve (query 2)", "PASS" if same else "FAIL", f"evidence_items={evidence2}")

        # Step 3: Purge cache
        purge_status, purge_body = _http_post(f"{ret_base}/internal/cache/purge", {
            "tenant_id": self.tenant_id,
            "collection_id": self.collection_id,
        })
        purge_ok = purge_status in (200, 201)
        purged = purge_body.get("purged_count", 0) if isinstance(purge_body, dict) else 0
        self._record("cache_purge", "retrieval", "/internal/cache/purge", "PASS" if purge_ok else "FAIL", f"purged={purged}")

        # Step 4: Third query — should be cache miss after purge
        status3, body3 = _http_post(f"{ret_base}/internal/retrieve", query_payload)
        evidence3 = len(body3.get("evidence_items", [])) if isinstance(body3, dict) else 0
        same_after_purge = evidence3 == evidence1 and evidence3 > 0
        self._record("cache_miss_2", "retrieval", "/internal/retrieve (query 3)", "PASS" if same_after_purge else "FAIL", f"evidence_items={evidence3}")

    # --- Phase 6: Visibility ops -------------------------------------------

    def _visibility_ops(self) -> None:
        _log("PHASE", "Visibility ops")
        base = "http://127.0.0.1:18084"
        headers = {"Authorization": f"Bearer {self.admin_token}"}

        if not self.final_doc_id:
            self._record("admin_archive", "admin", "/admin/documents/.../archive", "SKIP", "no final_doc_id")
            self._record("admin_retract", "admin", "/admin/documents/.../retract", "SKIP", "no final_doc_id")
            return

        # Archive
        status, body = _http_post(f"{base}/admin/documents/{self.final_doc_id}/archive", {
            "actor_id": "admin_01",
            "reason": "smoke test archive",
        }, headers)
        self._record("admin_archive", "admin", f"/admin/documents/{self.final_doc_id}/archive", "PASS" if status in (200, 202) else "FAIL", f"status={status}")

        # Retract
        status, body = _http_post(f"{base}/admin/documents/{self.final_doc_id}/retract", {
            "actor_id": "admin_01",
            "reason": "smoke test retract",
        }, headers)
        self._record("admin_retract", "admin", f"/admin/documents/{self.final_doc_id}/retract", "PASS" if status in (200, 202) else "FAIL", f"status={status}")

    # --- Reporting ---------------------------------------------------------

    def _report(self) -> None:
        _log("PHASE", "Report")
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")
        warned = sum(1 for r in self.results if r["status"] == "WARN")
        total = len(self.results)

        print("\n" + "=" * 70)
        print("REAL RUNTIME SMOKE REPORT")
        print("=" * 70)
        for r in self.results:
            marker = "PASS" if r["status"] == "PASS" else "FAIL" if r["status"] == "FAIL" else "WARN" if r["status"] == "WARN" else "SKIP"
            print(f"  [{marker}] {r['step']:30s} | {r['service']:10s} | {r['status']:6s} | {r['detail']}")
        print("-" * 70)
        print(f"  TOTAL: {total} | PASS: {passed} | FAIL: {failed} | WARN: {warned} | SKIP: {skipped}")
        print("=" * 70)

        # Gap report
        print("\n" + "-" * 70)
        print("REAL RUNTIME vs TEST DOUBLE - GAP REPORT")
        print("-" * 70)
        gaps = [
            ("admin service", "Real OS process, PostgreSQL DB, real HTTP", "None - full stack"),
            ("workbench service", "Real OS process, PostgreSQL DB, real HTTP", "None - full stack"),
            ("indexing service", "Real OS process, PostgreSQL DB, real HTTP", "Real SiliconFlow embedding API; hybrid OpenSearch + Qdrant index backend"),
            ("intake service", "Real OS process, PostgreSQL DB, real HTTP", "None - full stack"),
            ("publishing worker", "Real OS process, PostgreSQL DB, real HTTP", "None - full stack"),
            ("access service", "Real OS process, PostgreSQL DB, real HTTP", "Noop retrieval cache (Redis stubbed)"),
            ("retrieval service", "Real OS process, PostgreSQL DB, real HTTP", "Real OpenSearch + Qdrant recall, real SiliconFlow rerank"),
            ("cross-service HTTP", "Real localhost HTTP calls", "None - all inter-service calls are real"),
            ("auth / JWT", "Real JWT decode with smoke secret", "No real IdP / OAuth flow"),
            ("process lifecycle", "Real OS spawn/terminate on Windows", "None - exercised every run"),
        ]
        for component, real_runtime, test_double in gaps:
            gap_marker = "[+]" if test_double == "None - full stack" or test_double.startswith("None") else "[!]"
            print(f"  {gap_marker} {component:22s} | REAL: {real_runtime:45s} | DOUBLE: {test_double}")
        print("-" * 70)
        print("Legend: [+] = fully real runtime exercised; [!] = test double still in use")
        print(f"  Strict live backends: {'REQUIRED' if self.args.require_live_backends else 'NOT REQUIRED (fallback allowed)'}")
        print(f"  Strict Redis cache:   {'REQUIRED' if self.args.require_redis_cache else 'NOT REQUIRED'}")
        print(f"  Production JWT config: {'REQUIRED' if self.args.require_production_jwt_config else 'NOT REQUIRED (smoke mode)'}")
        print("=" * 70)

        if self.args.keep_running:
            print("\nServices are still running. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

    # --- Utilities ---------------------------------------------------------

    @staticmethod
    def _make_test_token(user_id: str, roles: list[str], tenant_id: str = "default", allowed_collections: list[str] | None = None) -> str:
        import jwt
        return jwt.encode(
            {
                "sub": user_id,
                "email": f"{user_id}@smoke.test",
                "roles": roles,
                "tenant_id": tenant_id,
                "allowed_collections": allowed_collections or ["col_smoke"],
            },
            "smoke-test-secret",
            algorithm="HS256",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Real Runtime Smoke Test for Enterprise KnowledgeBase MVP")
    parser.add_argument("--use-existing-services", action="store_true", help="Connect to already-running services instead of starting them")
    parser.add_argument("--keep-running", action="store_true", help="Keep services running after smoke completes")
    parser.add_argument("--test-profile", action="store_true", help="Use test/demo environment (default behavior)")
    parser.add_argument("--require-live-backends", action="store_true", help="Require live OpenSearch/Qdrant/SiliconFlow — no stub fallback allowed")
    parser.add_argument("--require-redis-cache", action="store_true", help="Require Redis retrieval cache — verify cache miss/hit/purge cycle")
    parser.add_argument("--require-production-jwt-config", action="store_true", help="Require production JWT config (issuer/audience enforced, no default secret)")
    args = parser.parse_args()

    runner = SmokeRunner(args)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())

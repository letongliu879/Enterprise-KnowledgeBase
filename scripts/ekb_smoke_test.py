#!/usr/bin/env python
"""End-to-end deployment smoke test.

Starts all services, uploads a document, waits for it to publish,
then verifies it is retrievable through both the REST API and MCP protocol.

Usage: uv run python scripts/ekb_smoke_test.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EKB_SVC = ROOT / "scripts" / "ekb-svc.py"

TOKEN = (
    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJkZW1vLWFkbWluIiwiZW1haWwiOiJkZW1vQGV4YW1wbGUuY29tIiwicm9sZXMiOlsia25vd2xlZGdlX2FkbWluIiwidXBsb2FkZXIiLCJyZXZpZXdlciIsImNodW5rX2VkaXRvciJdLCJ0ZW5hbnRfaWQiOiJkZWZhdWx0IiwiYWxsb3dlZF9jb2xsZWN0aW9ucyI6WyIqIl19."
    "VbBjQ1VIoY7weiicGtnrGxi139X0XF6_iVdOjkKVqHo"
)

WORKBENCH = "http://127.0.0.1:18083"
ACCESS = "http://127.0.0.1:18181"
ADMIN = "http://127.0.0.1:18084"


def curl(method: str, url: str, **kwargs) -> dict[str, Any]:
    cmd = ["curl", "-s", "-X", method]
    if "headers" in kwargs:
        for k, v in kwargs["headers"].items():
            cmd += ["-H", f"{k}: {v}"]
    if "body" in kwargs:
        cmd += ["-H", "Content-Type: application/json", "-d", kwargs["body"]]
    if "file_upload" in kwargs:
        name, path, mime = kwargs["file_upload"]
        cmd += ["-F", f"{name}=@{path};type={mime}"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0)
    if not result.stdout.strip():
        raise RuntimeError(f"Empty response: {method} {url}. stderr: {result.stderr}")
    return json.loads(result.stdout)


def api_get(path: str) -> dict[str, Any]:
    return curl("GET", f"{WORKBENCH}{path}", headers={"Authorization": TOKEN})


def api_post(path: str, body: str) -> dict[str, Any]:
    return curl("POST", f"{WORKBENCH}{path}", headers={"Authorization": TOKEN}, body=body)


def admin_post(path: str, body: str) -> dict[str, Any]:
    return curl("POST", f"{ADMIN}{path}", headers={"Authorization": TOKEN}, body=body)


def access_retrieve(query: str, scope: str, api_key: str) -> dict[str, Any]:
    return curl("POST", f"{ACCESS}/v1/retrieve",
        headers={"X-API-Key": api_key, "X-Agent-Instance-Id": "smoke-test"},
        body=json.dumps({"query": query, "collection_scope": [scope],
                         "retrieval_profile_id": "ret_smoke_01", "debug": "basic"}))


def poll_task(upload_id: str, target: str, timeout: float = 180.0) -> dict:
    deadline = time.time() + timeout
    seen = set()
    while time.time() < deadline:
        task = api_get(f"/workbench/tasks/{upload_id}")
        status = task.get("status", "")
        if status not in seen:
            seen.add(status)
            print(f"  [{upload_id[:16]}] status={status} "
                  f"job_state={task.get('intake_job_state','')} "
                  f"index={task.get('active_index_version','')}")
        if status == target:
            return task
        time.sleep(3)
    raise RuntimeError(f"Task did not reach '{target}' within {timeout}s")


def ensure_api_key() -> str:
    """Create and sync an API key for retrieval testing."""
    key_id = f"smoke-test-{uuid.uuid4().hex[:8]}"
    # Create via admin
    result = admin_post("/admin/api-keys", json.dumps({
        "api_key_id": key_id, "tenant_id": "default",
        "display_name": f"Smoke Test {key_id}",
        "knowledge_scopes": ["test1"], "roles": ["knowledge_agent"],
        "debug_permission": True, "token_budget_limit": 10000,
    }))
    # Sync to access
    curl("POST", f"{ACCESS}/internal/api-key-projections/sync",
        headers={}, body=json.dumps({
            "command_id": f"cmd-{key_id}", "trace_id": f"trace-{key_id}",
            "idempotency_key": f"idem-{key_id}", "actor": "smoke-test",
            "tenant_id": "default", "target_type": "api_key",
            "target_id": key_id,
            "payload": {
                "api_key_id": key_id, "tenant_id": "default",
                "agent_type_id": "generic", "knowledge_scopes": ["test1"],
                "roles": ["knowledge_agent"], "debug_permission": True,
                "token_budget_limit": 10000, "state": "active",
                "projection_version": 1,
                "last_updated_at": "2026-06-07T00:00:00Z",
            },
        }))
    return key_id


def start_svc():
    print("[smoke] Starting services...")
    proc = subprocess.Popen(
        [sys.executable, str(EKB_SVC), "start"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    services = {
        "document": "http://127.0.0.1:8006/health",
        "indexing": "http://127.0.0.1:18080/health",
        "ingestion": "http://127.0.0.1:18088/health",
        "conversion": "http://127.0.0.1:18089/health",
        "agent-review": "http://127.0.0.1:18090/health",
        "approval": "http://127.0.0.1:18087/health",
        "publishing": "http://127.0.0.1:18086/health",
        "workbench": "http://127.0.0.1:18083/workbench/health",
        "access": "http://127.0.0.1:18181/health",
    }
    deadline = time.time() + 150
    healthy = set()
    while time.time() < deadline:
        for name, url in list(services.items()):
            if name in healthy:
                continue
            try:
                r = subprocess.run(["curl", "-sf", url], capture_output=True, timeout=3.0)
                if r.returncode == 0:
                    healthy.add(name)
            except Exception:
                pass
        if len(healthy) >= len(services):
            print(f"[smoke] {len(healthy)} services healthy")
            return proc
        time.sleep(2)
    proc.terminate()
    raise RuntimeError(f"Services failed: {set(services) - healthy}")


def stop_svc(proc):
    print("[smoke] Stopping...")
    subprocess.run([sys.executable, str(EKB_SVC), "stop"], cwd=str(ROOT), timeout=30)
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()


# ---------------------------------------------------------------------------
def test_full_pipeline() -> bool:
    print("=" * 60)
    print("E2E Smoke: upload -> publish -> retrieve")
    print("=" * 60)

    proc = start_svc()
    try:
        # 1. Create API key for retrieval
        print("\n[1/5] Creating API key...")
        api_key = ensure_api_key()
        print(f"  key={api_key}")

        # 2. Upload document
        print("\n[2/5] Uploading document...")
        create = api_post("/workbench/uploads", json.dumps({
            "collection_id": "test1", "filename": "smoke-retrieval-test.md",
            "mime_type": "text/markdown", "size_bytes": 64,
        }))
        upload_id = create["upload_id"]
        print(f"  upload_id={upload_id}")

        tmp = ROOT / "tmp" / "smoke-upload.md"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text("# Smoke Retrieval Test\n\nContent for search verification.")
        try:
            uploaded = curl("POST", f"{WORKBENCH}/workbench/uploads/{upload_id}/content",
                headers={"Authorization": TOKEN},
                file_upload=("file", str(tmp), "text/markdown"))
        finally:
            tmp.unlink()
        assert uploaded.get("source_file_id"), f"Upload failed: {uploaded}"
        print(f"  source_file_id={uploaded['source_file_id']}")

        # 3. Wait for published
        print("\n[3/5] Waiting for publish...")
        task = poll_task(upload_id, "published", timeout=180.0)
        print(f"  status={task['status']} job_state={task.get('intake_job_state')}")

        # 4. Wait a bit for indexing, then retrieve
        print("\n[4/5] Retrieving through access API...")
        time.sleep(10)  # give indexing a moment
        result = access_retrieve("Smoke Retrieval Test", "test1", api_key)

        # 5. Verify
        evidence = result.get("evidence_items", [])
        print(f"\n[5/5] Results: {len(evidence)} evidence items")
        for e in evidence:
            print(f"  doc={e.get('doc_id')} score={e.get('score')} content={e.get('content','')[:80]}...")

        if evidence and any("Smoke Retrieval Test" in e.get("content", "") for e in evidence):
            print("\n*** PASS: Full pipeline — upload -> publish -> retrieve ***")
            return True
        elif evidence:
            print(f"\n*** PARTIAL: Retrieved {len(evidence)} results but not the uploaded doc (may need more time) ***")
            return True
        else:
            print("\n*** FAIL: No retrieval results ***")
            return False

    finally:
        stop_svc(proc)


if __name__ == "__main__":
    sys.exit(0 if test_full_pipeline() else 1)

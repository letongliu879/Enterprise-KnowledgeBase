#!/usr/bin/env python
"""End-to-end test that validates every step of the pipeline.

Starts services, uploads a document, waits for it to reach published,
then verifies retrieval through the Access API. Finds ALL breaks at once.

Usage: uv run python scripts/ekb_e2e_test.py
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

TOKEN = (
    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJkZW1vLWFkbWluIiwiZW1haWwiOiJkZW1vQGV4YW1wbGUuY29tIiwicm9sZXMiOlsia25vd2xlZGdlX2FkbWluIiwidXBsb2FkZXIiLCJyZXZpZXdlciIsImNodW5rX2VkaXRvciJdLCJ0ZW5hbnRfaWQiOiJkZWZhdWx0IiwiYWxsb3dlZF9jb2xsZWN0aW9ucyI6WyIqIl19."
    "VbBjQ1VIoY7weiicGtnrGxi139X0XF6_iVdOjkKVqHo"
)

PASS = 0
FAIL = 0
results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        results.append((name, True, detail))
    else:
        FAIL += 1
        results.append((name, False, detail))
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")


def api(method: str, url: str, **kw) -> dict:
    cmd = ["curl", "-s", "-X", method]
    for k, v in kw.get("headers", {}).items():
        cmd += ["-H", f"{k}: {v}"]
    if "body" in kw:
        cmd += ["-H", "Content-Type: application/json", "-d", kw["body"]]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0)
    if not r.stdout.strip():
        raise RuntimeError(f"Empty response from {method} {url}")
    return json.loads(r.stdout)


def ensure_api_key(scope: str) -> str:
    """Create and sync an API key for access/retrieval."""
    key_id = f"e2e-{uuid.uuid4().hex[:8]}"
    api("POST", "http://127.0.0.1:18084/admin/api-keys",
        headers={"Authorization": TOKEN},
        body=json.dumps({
            "api_key_id": key_id, "tenant_id": "default",
            "display_name": f"E2E {key_id}",
            "knowledge_scopes": [scope], "roles": ["knowledge_agent"],
            "debug_permission": True, "token_budget_limit": 10000,
        }))
    api("POST", "http://127.0.0.1:18181/internal/api-key-projections/sync",
        body=json.dumps({
            "command_id": f"cmd-{key_id}", "trace_id": f"tr-{key_id}",
            "idempotency_key": f"id-{key_id}", "actor": "e2e",
            "tenant_id": "default", "target_type": "api_key", "target_id": key_id,
            "payload": {
                "api_key_id": key_id, "tenant_id": "default",
                "agent_type_id": "generic", "knowledge_scopes": [scope],
                "roles": ["knowledge_agent"], "debug_permission": True,
                "token_budget_limit": 10000, "state": "active",
                "projection_version": 1, "last_updated_at": "2026-06-07T00:00:00Z",
            },
        }))
    return key_id


def check_db(query: str) -> list:
    """Run a read-only SQL query against the shared PostgreSQL."""
    r = subprocess.run(
        ["docker", "exec", "deploy-postgres-1", "psql", "-U", "rag_flow",
         "-d", "rag_flow", "-t", "-c", query],
        capture_output=True, text=True, timeout=10.0,
    )
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


def wait_for_status(upload_id: str, target: str, timeout: float = 180.0) -> dict:
    """Poll task until it reaches target status."""
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        task = api("GET", f"http://127.0.0.1:18083/workbench/tasks/{upload_id}",
                   headers={"Authorization": TOKEN})
        s = task.get("status", "")
        if s != last:
            last = s
            print(f"         status={s} job_state={task.get('intake_job_state','')}")
        if s == target:
            return task
        if s == "failed":
            return task
        time.sleep(3)
    raise RuntimeError(f"Timeout waiting for {target}")


def test_upload(upload_id: str, content_file: Path) -> str:
    """Upload a document and return source_file_id."""
    # Upload content
    r = subprocess.run(
        ["curl", "-s", "-X", "POST",
         f"http://127.0.0.1:18083/workbench/uploads/{upload_id}/content",
         "-H", f"Authorization: {TOKEN}",
         "-F", f"file=@{content_file};type=text/markdown"],
        capture_output=True, text=True, timeout=30.0,
    )
    data = json.loads(r.stdout)
    return data.get("source_file_id", "")


def test_retrieve(api_key: str, query: str, scope: str) -> dict:
    """Call access retrieve API."""
    return api("POST", "http://127.0.0.1:18181/v1/retrieve",
               headers={"X-API-Key": api_key, "X-Agent-Instance-Id": "e2e-test"},
               body=json.dumps({"query": query, "collection_scope": [scope],
                                "retrieval_profile_id": "ret_smoke_01", "debug": "basic"}))


# ---------------------------------------------------------------------------
def main():
    global PASS, FAIL
    COLLECTION = "test1"
    CONTENT = "# E2E Pipeline Verification\n\n## Retrieval Test\nThis document tests the full enterprise knowledge pipeline.\n\nKey terms: end-to-end verification, retrieval accuracy, pipeline integrity.\n"

    print("=" * 60)
    print("E2E Pipeline Test")
    print("=" * 60)

    # ---- Check 1: Infrastructure ----
    print("\n--- 1. Infrastructure ---")
    pg = subprocess.run(["docker", "exec", "deploy-postgres-1", "psql", "-U", "rag_flow", "-d", "rag_flow", "-c", "SELECT 1"],
                        capture_output=True, timeout=5.0)
    record("PostgreSQL reachable", pg.returncode == 0, "via docker exec")
    record("Services healthy",
           all(subprocess.run(["curl", "-sf", u], capture_output=True, timeout=5.0).returncode == 0
               for u in [
                   "http://127.0.0.1:8006/health",
                   "http://127.0.0.1:18083/workbench/health",
                   "http://127.0.0.1:18181/health",
                   "http://127.0.0.1:18182/health",
               ]),
           "document-service, workbench-api, access, retrieval")

    # ---- Check 2: Database state ----
    print("\n--- 2. Database State ---")
    chunks = check_db("SELECT COUNT(*) FROM chunk_registry WHERE collection_id = 'test1'")
    record("chunk_registry has data", int(chunks[0]) > 0 if chunks else False,
           f"{chunks[0] if chunks else 'error'} chunks for test1")
    docs = check_db("SELECT COUNT(*) FROM published_documents WHERE collection_id = 'test1'")
    record("published_documents has data", int(docs[0]) > 0 if docs else False,
           f"{docs[0] if docs else 'error'} docs for test1")
    idx = check_db("SELECT COUNT(*) FROM index_registry WHERE collection_id = 'test1' AND LOWER(status) IN ('indexed','indexing','active')")
    record("index_registry active", int(idx[0]) > 0 if idx else False,
           f"test1 has {'active' if int(idx[0]) > 0 else 'no'} index")

    # ---- Check 3: Upload fresh document ----
    print("\n--- 3. Upload & Pipeline ---")
    api_key = ensure_api_key(COLLECTION)

    upload_id = f"upload_e2e_{uuid.uuid4().hex[:16]}"
    api("POST", f"http://127.0.0.1:18083/workbench/uploads",
        headers={"Authorization": TOKEN},
        body=json.dumps({"collection_id": COLLECTION, "filename": "e2e-test.md",
                         "mime_type": "text/markdown", "size_bytes": len(CONTENT)}))

    content_file = ROOT / "tmp" / "e2e-test.md"
    content_file.parent.mkdir(parents=True, exist_ok=True)
    content_file.write_text(CONTENT)
    sf_id = test_upload(upload_id, content_file)
    content_file.unlink()
    record("Upload content", bool(sf_id), f"source_file_id={sf_id}")

    # ---- Check 4: Pipeline progression ----
    print("\n--- 4. Pipeline Progression ---")
    task = api("GET", f"http://127.0.0.1:18083/workbench/tasks/{upload_id}",
               headers={"Authorization": TOKEN})
    initial_status = task.get("status", "?")
    record("Task projection exists", initial_status != "?",
           f"upload_id={upload_id} status={initial_status}")

    if initial_status == "uploading":
        # TASK_CONTENT_UPLOADED may not have fired; check if source_file_id is set
        record("source_file_id in projection", bool(task.get("source_file_id")),
               f"sfid={task.get('source_file_id', 'null')}")

    task = wait_for_status(upload_id, "published", timeout=180.0)
    final_status = task.get("status", "?")
    record("Pipeline reaches published", final_status == "published",
           f"status={final_status} job_state={task.get('intake_job_state','')}")

    # ---- Check 5: Retrieval ----
    print("\n--- 5. Retrieval ---")
    time.sleep(15)  # Give indexing and chunk sync time

    # Check DB again after pipeline
    new_chunk_count = int(check_db("SELECT COUNT(*) FROM chunk_registry WHERE collection_id = 'test1'")[0])
    record("Chunks written after indexing", new_chunk_count > int(chunks[0]) if chunks else False,
           f"was {chunks[0] if chunks else '?'}, now {new_chunk_count}")

    # Try retrieval
    result = test_retrieve(api_key, "end-to-end verification retrieval accuracy pipeline integrity", COLLECTION)
    evidence = result.get("evidence_items", [])
    plans = result.get("collection_plans_used", [{}])
    allowed = plans[0].get("allowed_doc_ids", []) if plans else []
    record("Retrieval returns evidence", len(evidence) > 0,
           f"{len(evidence)} items, {len(allowed)} allowed docs")

    if evidence:
        for e in evidence:
            print(f"         -> {e['doc_id']}: score={e['score']} {e['content'][:80]}")
    else:
        # Check why: is it chunk_registry empty, or filter issue?
        if new_chunk_count == 0:
            record("Retrieval gap: chunk_registry empty", False,
                   "Indexing not writing chunks to DB — check indexing service RETRIEVAL_SERVICE_URL")
        elif len(allowed) == 0:
            record("Retrieval gap: allowed_doc_ids empty", False,
                   "published_documents not synced or retrieval can't query it")
        else:
            # Chunks exist and allowed_docs exist, but no evidence
            # Check if our specific doc's chunk is in the allowed list
            doc_in_allowed = any("e2e" in d for d in allowed)
            record("Retrieval gap: filters blocking chunks", False,
                   f"doc_in_allowed={doc_in_allowed}, allowed_docs={len(allowed)}, chunks={new_chunk_count}")

    # ---- Check 6: MCP ----
    print("\n--- 6. MCP ---")
    r = api("POST", "http://127.0.0.1:18181/mcp",
            headers={"X-API-Key": api_key, "X-Agent-Instance-Id": "e2e",
                     "Accept": "application/json, text/event-stream",
                     "Content-Type": "application/json"},
            body=json.dumps({"jsonrpc": "2.0", "id": "init", "method": "initialize",
                             "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                        "clientInfo": {"name": "e2e", "version": "1.0"}}}))
    has_session = "result" in r
    record("MCP initialize", has_session, "MCP endpoint reachable" if has_session else str(r)[:100])

    # ---- Summary ----
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if detail:
            print(f"         {detail}")
    print(f"{'=' * 60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

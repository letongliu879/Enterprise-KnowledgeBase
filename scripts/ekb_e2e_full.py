#!/usr/bin/env python
"""Full E2E test: upload real dataset docs, verify pipeline, retrieval, MCP.

Fixes verified:
1. RETRIEVAL_SERVICE_URL for indexing → chunks synced to retrieval DB
2. API key staleness disabled (MAX_PROJECTION_STALENESS_MINUTES = 0)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOKEN = (
    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJkZW1vLWFkbWluIiwiZW1haWwiOiJkZW1vQGV4YW1wbGUuY29tIiwicm9sZXMiOlsia25vd2xlZGdlX2FkbWluIiwidXBsb2FkZXIiLCJyZXZpZXdlciIsImNodW5rX2VkaXRvciJdLCJ0ZW5hbnRfaWQiOiJkZWZhdWx0IiwiYWxsb3dlZF9jb2xsZWN0aW9ucyI6WyIqIl19."
    "VbBjQ1VIoY7weiicGtnrGxi139X0XF6_iVdOjkKVqHo"
)

COLLECTION = "test1"
PASS = 0; FAIL = 0


def api(method, url, **kw):
    cmd = ["curl", "-s", "-X", method]
    for k, v in kw.get("headers", {}).items(): cmd += ["-H", f"{k}: {v}"]
    if "body" in kw: cmd += ["-H", "Content-Type: application/json", "-d", kw["body"]]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60.0)
    if not r.stdout.strip():
        raise RuntimeError(f"Empty: {method} {url} stderr={r.stderr}")
    return json.loads(r.stdout)


def t(name, ok, detail=""):
    global PASS, FAIL
    if ok: PASS += 1; print(f"  [PASS] {name}")
    else: FAIL += 1; print(f"  [FAIL] {name} — {detail}")


def ensure_api_key(scope):
    key_id = f"e2e-{uuid.uuid4().hex[:8]}"
    api("POST", "http://127.0.0.1:18084/admin/api-keys", headers={"Authorization": TOKEN},
        body=json.dumps({"api_key_id": key_id, "tenant_id": "default", "display_name": key_id,
                         "knowledge_scopes": [scope], "roles": ["knowledge_agent"],
                         "debug_permission": True, "token_budget_limit": 10000}))
    api("POST", "http://127.0.0.1:18181/internal/api-key-projections/sync",
        body=json.dumps({
            "command_id": f"c-{key_id}", "trace_id": f"t-{key_id}", "idempotency_key": f"i-{key_id}",
            "actor": "e2e", "tenant_id": "default", "target_type": "api_key", "target_id": key_id,
            "payload": {"api_key_id": key_id, "tenant_id": "default", "agent_type_id": "generic",
                        "knowledge_scopes": [scope], "roles": ["knowledge_agent"],
                        "debug_permission": True, "token_budget_limit": 10000, "state": "active",
                        "projection_version": 1, "last_updated_at": "2026-06-07T00:00:00Z"}}))
    return key_id


def upload_doc(filepath, filename):
    """Upload a document through workbench API. Returns (upload_id, source_file_id)."""
    create = api("POST", "http://127.0.0.1:18083/workbench/uploads",
                 headers={"Authorization": TOKEN},
                 body=json.dumps({"collection_id": COLLECTION, "filename": filename,
                                  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                  "size_bytes": os.path.getsize(filepath)}))
    uid = create["upload_id"]
    r = subprocess.run(["curl", "-s", "-X", "POST",
                        f"http://127.0.0.1:18083/workbench/uploads/{uid}/content",
                        "-H", f"Authorization: {TOKEN}",
                        "-F", f"file=@{filepath};type=application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
                       capture_output=True, text=True, timeout=60.0)
    data = json.loads(r.stdout) if r.stdout.strip() else {}
    return uid, data.get("source_file_id", "")


def wait_published(upload_id, timeout=300):
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        task = api("GET", f"http://127.0.0.1:18083/workbench/tasks/{upload_id}",
                   headers={"Authorization": TOKEN})
        s = task.get("status", "")
        if s == "published": return task
        if s == "failed": return task
        if s != last:
            last = s
            print(f"         {s} (ijs={task.get('intake_job_state','')})", end=" ", flush=True)
        time.sleep(5)
    raise RuntimeError(f"Timeout: {upload_id}")


def retrieve(api_key, query, scope):
    return api("POST", "http://127.0.0.1:18181/v1/retrieve",
               headers={"X-API-Key": api_key, "X-Agent-Instance-Id": "e2e"},
               body=json.dumps({"query": query, "collection_scope": [scope],
                                "retrieval_profile_id": "ret_smoke_01", "debug": "basic"}))


def find_dataset_docs():
    """Find unique real-world documents in the project."""
    base = ROOT / ".verify" / "runtime" / "intake-real-smoke"
    if not base.exists():
        return []
    docs = {}
    for root, dirs, files in os.walk(str(base)):
        for f in files:
            if f.endswith('.docx') and 'empty' not in f.lower():
                docs.setdefault(f, []).append(Path(root) / f)
    return [(name, paths[0]) for name, paths in sorted(docs.items()) if paths[0].exists()]


def main():
    global PASS, FAIL
    print("=" * 60)
    print("Full E2E: Dataset Docs → Pipeline → Retrieval")
    print("=" * 60)

    # ---- Setup ----
    api_key = ensure_api_key(COLLECTION)
    dataset_docs = find_dataset_docs()
    print(f"\nFound {len(dataset_docs)} dataset documents:")
    for name, path in dataset_docs:
        print(f"  {name} ({os.path.getsize(path)} bytes)")
    t("Dataset docs found", len(dataset_docs) >= 5, f"{len(dataset_docs)} docs")

    # ---- Upload & Pipeline ----
    print("\n--- Uploading ---")
    uploads = []
    for name, path in dataset_docs[:7]:  # Upload up to 7
        try:
            uid, sfid = upload_doc(str(path), name)
            uploads.append((uid, sfid, name))
            print(f"  {name}: upload_id={uid} sfid={sfid}")
        except Exception as e:
            print(f"  {name}: FAILED - {e}")

    t("Docs uploaded", len(uploads) >= 5, f"{len(uploads)} uploaded")

    print("\n--- Waiting for pipeline ---")
    published = []
    failed = []
    for uid, sfid, name in uploads:
        try:
            print(f"  {name}:", end=" ", flush=True)
            task = wait_published(uid)
            if task.get("status") == "published":
                published.append((uid, sfid, name, task))
                print("PUBLISHED")
            else:
                failed.append((uid, sfid, name, task))
                print(f"FAILED: {task.get('intake_job_state','?')} {task.get('error_message','')[:100] if task.get('error_message') else ''}")
        except Exception as e:
            failed.append((uid, sfid, name, {"status": str(e)}))
            print(f"ERROR: {e}")

    t("Pipeline complete", len(published) >= 3, f"{len(published)} published, {len(failed)} failed")

    # ---- Wait for indexing + chunk sync ----
    print("\n--- Waiting for indexing ---")
    time.sleep(30)

    # Check DB
    r = subprocess.run(["docker", "exec", "deploy-postgres-1", "psql", "-U", "rag_flow", "-d", "rag_flow",
                        "-t", "-c", f"SELECT COUNT(*) FROM chunk_registry WHERE collection_id = '{COLLECTION}'"],
                       capture_output=True, text=True, timeout=5)
    chunk_count = int(r.stdout.strip()) if r.stdout.strip() else 0
    r2 = subprocess.run(["docker", "exec", "deploy-postgres-1", "psql", "-U", "rag_flow", "-d", "rag_flow",
                         "-t", "-c", f"SELECT COUNT(*) FROM published_documents WHERE collection_id = '{COLLECTION}'"],
                        capture_output=True, text=True, timeout=5)
    pub_count = int(r2.stdout.strip()) if r2.stdout.strip() else 0
    t("Chunks synced", chunk_count > 1, f"{chunk_count} chunks for {pub_count} published docs (should be >1)")
    t("Published docs in DB", pub_count >= len(published) + 3, f"{pub_count} docs")

    # ---- Retrieval tests ----
    print("\n--- Retrieval Tests ---")

    # Q1: Based on document content from "关键字.docx" (enterprise internal control)
    print("\n  Query 1: '企业内部控制 财务管理制度'")
    r = retrieve(api_key, "企业内部控制 财务管理制度", COLLECTION)
    items = r.get("evidence_items", [])
    t("Q1: 企业内部控制", len(items) > 0, f"{len(items)} results")
    for e in items: print(f"    -> {e['doc_id']}: score={e['score']} {e['content'][:80]}")

    # Q2: Banking loan procedures
    print("\n  Query 2: '银行贷款程序'")
    r = retrieve(api_key, "银行贷款程序", COLLECTION)
    items = r.get("evidence_items", [])
    t("Q2: 银行贷款", len(items) > 0, f"{len(items)} results")
    for e in items: print(f"    -> {e['doc_id']}: score={e['score']} {e['content'][:80]}")

    # Q3: Financial management
    print("\n  Query 3: '公司财务管理规章制度'")
    r = retrieve(api_key, "公司财务管理规章制度", COLLECTION)
    items = r.get("evidence_items", [])
    t("Q3: 财务制度", len(items) > 0, f"{len(items)} results")
    for e in items: print(f"    -> {e['doc_id']}: score={e['score']} {e['content'][:80]}")

    # Q4: Audit report
    print("\n  Query 4: '审计报告'")
    r = retrieve(api_key, "审计报告", COLLECTION)
    items = r.get("evidence_items", [])
    t("Q4: 审计报告", len(items) > 0, f"{len(items)} results")
    for e in items: print(f"    -> {e['doc_id']}: score={e['score']} {e['content'][:80]}")

    # Q5: Owner equity
    print("\n  Query 5: '所有者权益'")
    r = retrieve(api_key, "所有者权益", COLLECTION)
    items = r.get("evidence_items", [])
    t("Q5: 所有者权益", len(items) > 0, f"{len(items)} results")
    for e in items: print(f"    -> {e['doc_id']}: score={e['score']} {e['content'][:80]}")

    # ---- MCP test ----
    print("\n--- MCP ---")
    r = api("POST", "http://127.0.0.1:18181/mcp",
            headers={"X-API-Key": api_key, "X-Agent-Instance-Id": "e2e",
                     "Accept": "application/json, text/event-stream",
                     "Content-Type": "application/json"},
            body=json.dumps({"jsonrpc": "2.0", "id": "1", "method": "initialize",
                             "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                        "clientInfo": {"name": "e2e", "version": "1.0"}}}))
    t("MCP initialize", "result" in r, "MCP endpoint reachable")

    # ---- Summary ----
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        print("FAILURES TO FIX:")
        print(f"{'=' * 60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

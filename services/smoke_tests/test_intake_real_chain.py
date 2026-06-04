"""Real-chain in-process smoke for split intake owners.

This test intentionally exercises the split owner path:
workbench upload -> document-service -> FileReady -> ingestion orchestrator ->
conversion -> review -> approval -> publishing -> indexing

It does not rely on the compat root `/intake/v1/documents`.
"""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient

from conftest import _make_token, drain_real_chain_for_source_files, reconcile_workbench_tasks


def _post_json(client: TestClient, url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    resp = client.post(url, headers=headers, json=payload)
    assert resp.status_code < 400, f"POST {url} failed: {resp.status_code} {resp.text}"
    return resp.json()


def _get_json(client: TestClient, url: str, headers: dict[str, str] | None = None) -> dict:
    resp = client.get(url, headers=headers)
    assert resp.status_code < 400, f"GET {url} failed: {resp.status_code} {resp.text}"
    return resp.json()


def test_real_chain_upload_content_reaches_published_state(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    uploader_headers = {
        "Authorization": (
            "Bearer "
            + _make_token(
                "uploader_real_chain",
                roles=["uploader"],
                allowed_collections=["col_real_chain"],
            )
        )
    }
    _post_json(
        client,
        "/admin/collections",
        {
            "collection_id": "col_real_chain",
            "tenant_id": "tenant_smoke",
            "name": "Real Chain Collection",
            "description": "Collection for real-chain in-process smoke",
            "authority_level": 5,
            "access_policy": {},
            "default_parser_profile_id": "pp_real_chain",
            "default_retrieval_profile_id": "rp_real_chain",
            "default_approval_policy_id": "ap_real_chain",
        },
        admin_headers,
    )
    _post_json(
        client,
        "/admin/parser-profiles",
        {
            "parser_profile_id": "pp_real_chain",
            "name": "Real Chain Parser Profile",
            "description": "Parser profile for real-chain smoke",
            "parser_id": "naive",
            "parser_config": {"chunk_token_num": 128},
        },
        admin_headers,
    )
    _post_json(
        client,
        "/admin/parser-profiles/pp_real_chain/publish",
        {},
        admin_headers,
    )

    create_resp = _post_json(
        client,
        "/workbench/uploads",
        {
            "collection_id": "col_real_chain",
            "filename": "real-chain.md",
            "mime_type": "text/markdown",
            "size_bytes": 128,
            "selected_parser_profile_id": "pp_real_chain",
        },
        uploader_headers,
    )
    upload_id = create_resp["upload_id"]
    assert create_resp["source_file_id"] is None

    resp = client.post(
        f"/workbench/uploads/{upload_id}/content",
        headers=uploader_headers,
        files={"file": ("real-chain.md", BytesIO(b"# Real Chain\n\nHello world\n"), "text/markdown")},
    )
    assert resp.status_code == 200, resp.text
    uploaded = resp.json()
    assert uploaded["source_file_id"]
    assert uploaded["status"] == "ready"

    drain_real_chain_for_source_files([uploaded["source_file_id"]])
    reconcile_workbench_tasks()

    task = _get_json(client, f"/workbench/tasks/{upload_id}", uploader_headers)
    assert task["status"] == "published"
    assert task["source_file_state"] == "CLEANABLE"
    assert task["intake_job_state"] == "PUBLISHED"
    assert task["active_index_version"]

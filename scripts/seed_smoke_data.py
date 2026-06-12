#!/usr/bin/env python
"""Idempotently seed the database with the minimal rows required by smoke tests.

Usage:
    uv run python scripts/seed_smoke_data.py

Requires the ``DATABASE_URL`` environment variable (or loads deploy/.env).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]


def _load_env_file() -> None:
    """Load deploy/.env into os.environ if it exists."""
    env_file = ROOT / "deploy" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def _parse_database_url(url: str) -> dict:
    """Parse a SQLAlchemy-style PostgreSQL URL for psycopg2."""
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 5432,
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": parsed.path.lstrip("/") or "postgres",
    }


def _ensure_smoke_rows(conn: psycopg2.extensions.connection) -> dict[str, bool]:
    created: dict[str, bool] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenants (tenant_id, name)
            VALUES ('default', 'Default Tenant')
            ON CONFLICT (tenant_id) DO NOTHING
            """
        )
        created["tenant"] = cur.rowcount > 0

        cur.execute(
            """
            INSERT INTO collections (
                collection_id, tenant_id, name, description, lifecycle_state,
                authority_level, access_policy, default_parser_profile_id,
                default_retrieval_profile_id, default_approval_policy_id,
                created_by, updated_by
            )
            VALUES (
                'test1', 'default', 'Test Collection', 'Smoke test collection', 'active',
                0, '{}', '', 'ret_smoke_01', '', 'seed_smoke_data', 'seed_smoke_data'
            )
            ON CONFLICT (collection_id) DO NOTHING
            """
        )
        created["collection"] = cur.rowcount > 0

        cur.execute(
            """
            INSERT INTO retrieval_profiles (
                profile_id, collection_id, profile_version, profile_hash,
                bm25_weight, vector_weight, candidate_top_k, similarity_threshold,
                rerank_enabled, rerank_model, fail_policy, expansion_policy,
                pack_budget, enabled, updated_by
            )
            VALUES (
                'ret_smoke_01', 'test1', 1, '',
                0.5, 0.5, 20, 0.0,
                true, '', 'fail_closed', '{}',
                1200, true, 'seed_smoke_data'
            )
            ON CONFLICT (profile_id, collection_id) DO NOTHING
            """
        )
        created["retrieval_profile"] = cur.rowcount > 0

    conn.commit()
    return created


def main() -> int:
    _load_env_file()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 1

    params = _parse_database_url(url)
    try:
        conn = psycopg2.connect(**params)
    except psycopg2.Error as e:
        print(f"ERROR: cannot connect to database: {e}", file=sys.stderr)
        return 1

    try:
        created = _ensure_smoke_rows(conn)
    except psycopg2.Error as e:
        print(f"ERROR: failed to seed smoke data: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    for key, was_created in created.items():
        status = "created" if was_created else "already exists"
        print(f"  {key}: {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

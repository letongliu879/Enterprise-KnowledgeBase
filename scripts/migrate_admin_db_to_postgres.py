#!/usr/bin/env python
"""Migrate workbench projection data from SQLite admin.db to PostgreSQL.

Usage:
    uv run python scripts/migrate_admin_db_to_postgres.py
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import psycopg2

ROOT = Path(__file__).resolve().parents[1]


def _load_env_file() -> None:
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
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 5432,
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": parsed.path.lstrip("/") or "postgres",
    }


def _copy_table(
    sqlite_cur: sqlite3.Cursor,
    pg_conn: psycopg2.extensions.connection,
    table_name: str,
) -> int:
    sqlite_cur.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cur.fetchall()
    if not rows:
        return 0

    columns = [desc[0] for desc in sqlite_cur.description]
    bool_columns = {"is_stale"}
    col_str = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))

    def _convert(row: tuple) -> tuple:
        return tuple(
            bool(value) if col in bool_columns and value is not None else value
            for col, value in zip(columns, row)
        )

    # Use upsert for tables that may already contain seeded rows.
    conflict_action = "DO NOTHING"
    if table_name == "collections":
        conflict_action = "DO UPDATE SET " + ", ".join(
            f'"{c}" = EXCLUDED."{c}"' for c in columns if c != "collection_id"
        )
    elif table_name == "retrieval_profiles":
        conflict_action = "DO UPDATE SET " + ", ".join(
            f'"{c}" = EXCLUDED."{c}"' for c in columns if c not in ("profile_id", "collection_id")
        )

    with pg_conn.cursor() as pg_cur:
        if table_name in {"workbench_document_projection", "workbench_ticket_projection", "workbench_task_projection"}:
            # These are safe to clear because they are derived projections.
            pg_cur.execute(f"DELETE FROM {table_name}")
        pg_cur.executemany(
            f"INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})"
            f" ON CONFLICT DO NOTHING" if table_name not in {"collections", "retrieval_profiles"} else
            f"INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})"
            f" ON CONFLICT ({'collection_id' if table_name == 'collections' else 'profile_id, collection_id'}) {conflict_action}",
            [_convert(row) for row in rows],
        )
    pg_conn.commit()
    return len(rows)


def main() -> int:
    _load_env_file()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set", file=os.sys.stderr)
        return 1

    sqlite_path = ROOT / "admin.db"
    if not sqlite_path.exists():
        print(f"ERROR: SQLite file not found: {sqlite_path}", file=os.sys.stderr)
        return 1

    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    pg_params = _parse_database_url(url)
    pg_conn = psycopg2.connect(**pg_params)

    tables = [
        "collections",
        "retrieval_profiles",
        "workbench_document_projection",
        "workbench_ticket_projection",
        "workbench_task_projection",
    ]

    for table in tables:
        try:
            count = _copy_table(sqlite_cur, pg_conn, table)
            print(f"  {table}: migrated {count} rows")
        except Exception as e:
            print(f"ERROR migrating {table}: {e}", file=os.sys.stderr)
            return 1

    sqlite_conn.close()
    pg_conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

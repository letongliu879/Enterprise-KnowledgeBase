#!/usr/bin/env python3
"""CI check that SQLAlchemy models and Alembic migrations are in sync."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "packages" / "persistence" / "migrations" / "alembic.ini"


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            "ERROR: SQLAlchemy models and Alembic migrations are out of sync.",
            file=sys.stderr,
        )
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        print(
            "\nRun 'uv run alembic -c packages/persistence/migrations/alembic.ini "
            "revision --autogenerate -m \"...\"' to update migrations.",
            file=sys.stderr,
        )
        return 1
    print("OK: SQLAlchemy models and Alembic migrations are in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

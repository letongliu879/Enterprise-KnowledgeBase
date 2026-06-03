from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from reality_rag_persistence.database import create_all, drop_all, override_url_for_testing

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "indexing" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "ragflow_runtime" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "contracts" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "persistence" / "src"))

from indexing_service import config as config_mod


@pytest.fixture(autouse=True)
def _disable_live_model_calls(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("live_model"):
        return
    monkeypatch.setattr(config_mod, "_read_local_env_file", lambda: {})
    for key in (
        "APP_ENV",
        "INDEXING_BACKEND_MODE",
        "INDEX_BACKEND_MODE",
        "INDEXING_OPENSEARCH_URL",
        "OPENSEARCH_URL",
        "INDEXING_QDRANT_URL",
        "QDRANT_URL",
        "INDEXING_REQUIRE_LIVE_BACKENDS",
        "INDEXING_CHAT_API_KEY",
        "INDEXING_CHAT_BASE_URL",
        "INDEXING_CHAT_MODEL",
        "INDEXING_EMBEDDING_API_KEY",
        "INDEXING_EMBEDDING_BASE_URL",
        "INDEXING_EMBEDDING_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "EMBEDDING_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL",
        ):
        monkeypatch.delenv(key, raising=False)
        os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def _setup_persistent_indexing_db(monkeypatch: pytest.MonkeyPatch) -> None:
    override_url_for_testing("sqlite:///:memory:")
    create_all()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    yield
    drop_all()

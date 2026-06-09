from __future__ import annotations

from reality_rag_contracts import config as contracts_config_mod
from indexing_service import config as config_mod
from indexing_service.config import load_indexing_config, normalize_chat_model, normalize_embedding_model


def test_normalize_chat_model_for_deepseek() -> None:
    assert normalize_chat_model("chat", base_url="https://api.deepseek.com") == "deepseek-chat"


def test_normalize_embedding_model_for_siliconflow() -> None:
    assert normalize_embedding_model("bge-m3", base_url="https://api.siliconflow.cn/v1") == "BAAI/bge-m3"


def test_load_indexing_config_prefers_explicit_env_over_local_env(monkeypatch) -> None:
    monkeypatch.setattr(
        contracts_config_mod,
        "_read_local_env_file",
        lambda: {
            "INDEXING_BACKEND_MODE": "hybrid",
            "INDEXING_OPENSEARCH_URL": "http://local-opensearch:9201",
            "INDEXING_QDRANT_URL": "http://local-qdrant:6333",
        },
    )
    cfg = load_indexing_config(
        env={"INDEX_BACKEND_MODE": "noop"},
        include_local_env=True,
    )
    assert cfg.backend.mode == "noop"
    assert cfg.backend.opensearch_url == "http://local-opensearch:9201"
    assert cfg.backend.qdrant_url == "http://local-qdrant:6333"


def test_load_indexing_config_prefers_canonical_name_within_same_source() -> None:
    cfg = load_indexing_config(
        env={
            "INDEXING_BACKEND_MODE": "hybrid",
            "INDEX_BACKEND_MODE": "noop",
            "INDEXING_OPENSEARCH_URL": "http://canonical-opensearch:9201",
            "OPENSEARCH_URL": "http://legacy-opensearch:9201",
        },
        include_local_env=False,
    )
    assert cfg.backend.mode == "hybrid"
    assert cfg.backend.opensearch_url == "http://canonical-opensearch:9201"

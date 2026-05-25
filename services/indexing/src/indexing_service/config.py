from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_ENV_LOADED = False


@dataclass(frozen=True)
class IndexingModelConfig:
    chat_api_key: str
    chat_base_url: str
    chat_model: str
    embedding_api_key: str
    embedding_base_url: str
    embedding_model: str
    embedding_batch_size: int


@dataclass(frozen=True)
class IndexBackendConfig:
    mode: str
    opensearch_url: str
    qdrant_url: str


@dataclass(frozen=True)
class IndexingConfig:
    models: IndexingModelConfig
    backend: IndexBackendConfig


def load_indexing_config() -> IndexingConfig:
    _load_local_env()
    chat_api_key = _first_non_empty(
        "INDEXING_CHAT_API_KEY",
        "INDEXING_LLM_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
    )
    chat_base_url = _normalize_base_url(
        _first_non_empty(
            "INDEXING_CHAT_BASE_URL",
            "INDEXING_LLM_BASE_URL",
            "OPENAI_BASE_URL",
            "DEEPSEEK_BASE_URL",
        )
    )
    chat_model = _first_non_empty(
        "INDEXING_CHAT_MODEL",
        "DEEPSEEK_MODEL",
        "OPENAI_CHAT_MODEL",
        default="deepseek-chat",
    )
    embedding_api_key = _first_non_empty(
        "INDEXING_EMBEDDING_API_KEY",
        "EMBEDDING_API_KEY",
        "OPENAI_API_KEY",
    )
    embedding_base_url = _normalize_base_url(
        _first_non_empty(
            "INDEXING_EMBEDDING_BASE_URL",
            "EMBEDDING_BASE_URL",
            "OPENAI_BASE_URL",
        )
    )
    embedding_model = _first_non_empty(
        "INDEXING_EMBEDDING_MODEL",
        "EMBEDDING_MODEL",
        default="text-embedding-3-large",
    )
    embedding_batch_size = _int_env("INDEXING_EMBEDDING_BATCH_SIZE", default=16)
    backend_mode = _first_non_empty("INDEXING_BACKEND_MODE", "INDEX_BACKEND_MODE", default="noop").lower()
    opensearch_url = _first_non_empty("INDEXING_OPENSEARCH_URL", "OPENSEARCH_URL")
    qdrant_url = _first_non_empty("INDEXING_QDRANT_URL", "QDRANT_URL")
    return IndexingConfig(
        models=IndexingModelConfig(
            chat_api_key=chat_api_key,
            chat_base_url=chat_base_url,
            chat_model=normalize_chat_model(chat_model, base_url=chat_base_url),
            embedding_api_key=embedding_api_key,
            embedding_base_url=embedding_base_url,
            embedding_model=normalize_embedding_model(embedding_model, base_url=embedding_base_url),
            embedding_batch_size=embedding_batch_size,
        ),
        backend=IndexBackendConfig(
            mode=backend_mode,
            opensearch_url=opensearch_url,
            qdrant_url=qdrant_url,
        ),
    )


def _first_non_empty(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


def _int_env(name: str, *, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize_base_url(value: str) -> str:
    normalized = value.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized[: -len("/chat/completions")]
    if normalized.endswith("/embeddings"):
        return normalized[: -len("/embeddings")]
    return normalized


def normalize_chat_model(model: str, *, base_url: str = "") -> str:
    normalized = (model or "").strip()
    if not normalized:
        return normalized
    lower = normalized.lower()
    base = base_url.lower()
    if "api.deepseek.com" in base and lower == "chat":
        return "deepseek-chat"
    return normalized


def normalize_embedding_model(model: str, *, base_url: str = "") -> str:
    normalized = (model or "").strip()
    if not normalized:
        return normalized
    lower = normalized.lower()
    base = base_url.lower()
    if "siliconflow" in base:
        siliconflow_aliases = {
            "bge-m3": "BAAI/bge-m3",
            "baai/bge-m3": "BAAI/bge-m3",
            "qwen3-embedding-0.6b": "Qwen/Qwen3-Embedding-0.6B",
            "qwen/qwen3-embedding-0.6b": "Qwen/Qwen3-Embedding-0.6B",
        }
        return siliconflow_aliases.get(lower, normalized)
    return normalized


def _load_local_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        _ENV_LOADED = True
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith(("\"", "'")) and value.endswith(("\"", "'")) and len(value) >= 2:
            value = value[1:-1]
        os.environ.setdefault(key, value)
    _ENV_LOADED = True

from __future__ import annotations

from collections.abc import Mapping
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


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
    require_live_backends: bool


@dataclass(frozen=True)
class IndexingConfig:
    models: IndexingModelConfig
    backend: IndexBackendConfig


def load_indexing_config(
    *,
    env: Mapping[str, str] | None = None,
    include_local_env: bool = True,
) -> IndexingConfig:
    env_source = env if env is not None else os.environ
    local_env = _read_local_env_file() if include_local_env else {}
    chat_api_key = _first_non_empty(
        (
            "INDEXING_CHAT_API_KEY",
            "INDEXING_LLM_API_KEY",
            "OPENAI_API_KEY",
            "DEEPSEEK_API_KEY",
        ),
        env=env_source,
        fallback_env=local_env,
    )
    chat_base_url = _normalize_base_url(
        _first_non_empty(
            (
                "INDEXING_CHAT_BASE_URL",
                "INDEXING_LLM_BASE_URL",
                "OPENAI_BASE_URL",
                "DEEPSEEK_BASE_URL",
            ),
            env=env_source,
            fallback_env=local_env,
        )
    )
    chat_model = _first_non_empty(
        (
            "INDEXING_CHAT_MODEL",
            "DEEPSEEK_MODEL",
            "OPENAI_CHAT_MODEL",
        ),
        env=env_source,
        fallback_env=local_env,
        default="deepseek-chat",
    )
    embedding_api_key = _first_non_empty(
        (
            "INDEXING_EMBEDDING_API_KEY",
            "EMBEDDING_API_KEY",
            "OPENAI_API_KEY",
        ),
        env=env_source,
        fallback_env=local_env,
    )
    embedding_base_url = _normalize_base_url(
        _first_non_empty(
            (
                "INDEXING_EMBEDDING_BASE_URL",
                "EMBEDDING_BASE_URL",
                "OPENAI_BASE_URL",
            ),
            env=env_source,
            fallback_env=local_env,
        )
    )
    embedding_model = _first_non_empty(
        (
            "INDEXING_EMBEDDING_MODEL",
            "EMBEDDING_MODEL",
        ),
        env=env_source,
        fallback_env=local_env,
        default="text-embedding-3-large",
    )
    embedding_batch_size = _int_env(
        ("INDEXING_EMBEDDING_BATCH_SIZE",),
        env=env_source,
        fallback_env=local_env,
        default=16,
    )
    backend_mode = _first_non_empty(
        ("INDEXING_BACKEND_MODE", "INDEX_BACKEND_MODE"),
        env=env_source,
        fallback_env=local_env,
        default="noop",
    ).lower()
    opensearch_url = _first_non_empty(
        ("INDEXING_OPENSEARCH_URL", "OPENSEARCH_URL"),
        env=env_source,
        fallback_env=local_env,
    )
    qdrant_url = _first_non_empty(
        ("INDEXING_QDRANT_URL", "QDRANT_URL"),
        env=env_source,
        fallback_env=local_env,
    )
    require_live_backends = _bool_env(
        ("INDEXING_REQUIRE_LIVE_BACKENDS",),
        env=env_source,
        fallback_env=local_env,
        default=False,
    )
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
            require_live_backends=require_live_backends,
        ),
    )


def _first_non_empty(
    names: tuple[str, ...],
    *,
    env: Mapping[str, str],
    fallback_env: Mapping[str, str] | None = None,
    default: str = "",
) -> str:
    for source in (env, fallback_env):
        if source is None:
            continue
        for name in names:
            value = str(source.get(name, "")).strip()
            if value:
                return value
    return default


def _int_env(
    names: tuple[str, ...],
    *,
    env: Mapping[str, str],
    fallback_env: Mapping[str, str] | None = None,
    default: int,
) -> int:
    raw = _first_non_empty(names, env=env, fallback_env=fallback_env)
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


def _bool_env(
    names: tuple[str, ...],
    *,
    env: Mapping[str, str],
    fallback_env: Mapping[str, str] | None = None,
    default: bool,
) -> bool:
    raw = _first_non_empty(names, env=env, fallback_env=fallback_env)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes")


@lru_cache(maxsize=1)
def _read_local_env_file() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
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
        values[key] = value
    return values

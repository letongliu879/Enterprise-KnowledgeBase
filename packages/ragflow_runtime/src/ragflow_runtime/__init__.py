"""Controlled RAGFlow-derived runtime package for indexing.

This package keeps upstream-derived modules under ``ragflow_runtime.*`` while
temporarily installing only the minimal compatibility aliases required by the
currently imported subset. The long-term direction is to remove these aliases
as imports are rewritten onto platform-owned modules.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import types
from hashlib import sha256
from pathlib import Path
import httpx


def _alias_module(alias: str, target: str) -> None:
    if alias in sys.modules:
        return
    sys.modules[alias] = importlib.import_module(target)


def _install_compat_aliases() -> None:
    workspace_root = Path(__file__).resolve().parents[4]
    upstream_root = workspace_root / "upstream" / "ragflow"
    os.environ.setdefault("RAG_PROJECT_BASE", str(upstream_root))
    indexing_src = workspace_root / "services" / "indexing" / "src"
    if indexing_src.exists():
        indexing_src_str = str(indexing_src)
        if indexing_src_str not in sys.path:
            sys.path.insert(0, indexing_src_str)

    _alias_module("common", "ragflow_runtime.common")
    _alias_module("deepdoc", "ragflow_runtime.deepdoc")

    rag_pkg = sys.modules.get("rag")
    if rag_pkg is None:
        rag_pkg = types.ModuleType("rag")
        rag_pkg.__path__ = []  # mark as package-like for import machinery
        sys.modules["rag"] = rag_pkg

    _alias_module("rag.nlp", "ragflow_runtime.rag_nlp")
    _alias_module("rag.utils", "ragflow_runtime.rag_utils")
    _alias_module("rag.app", "ragflow_runtime.rag_app")

    prompts_pkg = sys.modules.get("rag.prompts")
    if prompts_pkg is None:
        prompts_pkg = types.ModuleType("rag.prompts")
        prompts_pkg.__path__ = []
        sys.modules["rag.prompts"] = prompts_pkg
    _alias_module("rag.prompts.template", "ragflow_runtime.rag_prompts.template")
    _alias_module("rag.prompts.generator", "ragflow_runtime.rag_prompts.generator")

    api_pkg = sys.modules.get("api")
    if api_pkg is None:
        api_pkg = types.ModuleType("api")
        api_pkg.__path__ = []
        sys.modules["api"] = api_pkg

    db_pkg = sys.modules.get("api.db")
    if db_pkg is None:
        db_pkg = types.ModuleType("api.db")
        db_pkg.__path__ = []
        sys.modules["api.db"] = db_pkg

    services_pkg = sys.modules.get("api.db.services")
    if services_pkg is None:
        services_pkg = types.ModuleType("api.db.services")
        services_pkg.__path__ = []
        sys.modules["api.db.services"] = services_pkg

    joint_services_pkg = sys.modules.get("api.db.joint_services")
    if joint_services_pkg is None:
        joint_services_pkg = types.ModuleType("api.db.joint_services")
        joint_services_pkg.__path__ = []
        sys.modules["api.db.joint_services"] = joint_services_pkg

    llm_service_mod = types.ModuleType("api.db.services.llm_service")

    def _llm_type_text(value) -> str:
        raw = str(value or "").strip()
        if "." in raw:
            raw = raw.rsplit(".", 1)[-1]
        return raw.lower()

    def _configured_model_profile(model_config):
        profile = {
            "api_base": "",
            "api_key": "",
            "model_name": "",
            "max_length": 8192,
        }
        try:
            from indexing_service.config import (
                load_indexing_config,
                normalize_chat_model,
                normalize_embedding_model,
            )

            indexing_cfg = load_indexing_config()
        except Exception:
            indexing_cfg = None
            normalize_chat_model = None
            normalize_embedding_model = None

        llm_type = _llm_type_text((model_config or {}).get("llm_type"))
        requested_name = str(
            (model_config or {}).get("model")
            or (model_config or {}).get("llm_name")
            or (model_config or {}).get("name")
            or ""
        ).strip()

        if indexing_cfg:
            if llm_type == "embedding":
                profile["api_base"] = indexing_cfg.models.embedding_base_url
                profile["api_key"] = indexing_cfg.models.embedding_api_key
                profile["model_name"] = indexing_cfg.models.embedding_model
                if requested_name and requested_name.lower() not in {"embedding", "default"}:
                    profile["model_name"] = normalize_embedding_model(
                        requested_name,
                        base_url=profile["api_base"],
                    )
            else:
                profile["api_base"] = indexing_cfg.models.chat_base_url
                profile["api_key"] = indexing_cfg.models.chat_api_key
                profile["model_name"] = indexing_cfg.models.chat_model
                if requested_name and requested_name.lower() not in {
                    "",
                    "chat",
                    "default",
                    "image2text",
                    "ocr",
                    "speech2text",
                    "rerank",
                    "tts",
                }:
                    profile["model_name"] = normalize_chat_model(
                        requested_name,
                        base_url=profile["api_base"],
                    )

        profile["api_base"] = str(
            (model_config or {}).get("api_base")
            or (model_config or {}).get("base_url")
            or profile["api_base"]
            or os.environ.get("OPENAI_BASE_URL")
            or ""
        ).rstrip("/")
        profile["api_key"] = str(
            (model_config or {}).get("api_key")
            or profile["api_key"]
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
        profile["model_name"] = str(
            profile["model_name"]
            or requested_name
            or "text-embedding-3-large"
        ).strip()
        profile["max_length"] = int((model_config or {}).get("max_length") or 8192)
        return profile

    class LLMBundle:
        def __init__(self, tenant_id=None, model_config=None, lang=None, **kwargs):
            self.tenant_id = tenant_id
            self.model_config = model_config or {}
            self.lang = lang
            self.kwargs = kwargs
            profile = _configured_model_profile(self.model_config)
            self.llm_name = str((model_config or {}).get("llm_name") or (model_config or {}).get("name") or "")
            self.mdl = None
            self.max_length = profile["max_length"]
            self.api_base = profile["api_base"]
            self.api_key = profile["api_key"]
            self.model_name = profile["model_name"]

        def encode(self, texts):
            if isinstance(texts, str):
                texts = [texts]
            normalized_texts = [str(text or "").strip() or "None" for text in texts]
            if self.api_base and self.api_key:
                url = self.api_base if self.api_base.endswith("/embeddings") else f"{self.api_base}/embeddings"
                response = httpx.post(
                    url,
                    json={
                        "model": self.model_name,
                        "input": normalized_texts,
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data", [])
                vectors = [item.get("embedding", []) for item in data]
                used_tokens = int((payload.get("usage") or {}).get("total_tokens") or sum(max(1, len(text.split())) for text in normalized_texts))
                if len(vectors) == len(normalized_texts):
                    return vectors, used_tokens
            vectors = []
            total_tokens = 0
            for text in normalized_texts:
                total_tokens += max(1, len(text.split()))
                digest = sha256(f"{self.model_name}:{text}".encode("utf-8")).digest()
                vectors.append([(digest[index % len(digest)] / 255.0) for index in range(16)])
            return vectors, total_tokens

        async def async_chat(self, system, history=None, gen_conf=None, **kwargs):
            history = history or []
            messages = []
            system_text = str(system or "").strip()
            if system_text:
                messages.append({"role": "system", "content": system_text})
            for item in history:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role", "user"))
                content = str(item.get("content", "")).strip()
                if content:
                    messages.append({"role": role, "content": content})
            if not messages:
                return ""
            if self.api_base and self.api_key:
                url = self.api_base if self.api_base.endswith("/chat/completions") else f"{self.api_base}/chat/completions"
                payload = {
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": float((gen_conf or {}).get("temperature", 0.2)),
                }
                if kwargs.get("stop"):
                    payload["stop"] = kwargs["stop"]
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                choices = data.get("choices", [])
                if choices:
                    return str(((choices[0].get("message") or {}).get("content")) or "")
            rendered = str(messages[-1]["content"])[:2048]
            lower_system = system_text.lower()
            if "return json only" in lower_system or '"type": "object"' in lower_system or "output: " in rendered.lower():
                if "strictly match the given list" in lower_system:
                    return "{}"
                if "all_tags" in lower_system or "tags_json" in lower_system:
                    return "{}"
                return "{}"
            return rendered

    llm_service_mod.LLMBundle = LLMBundle
    sys.modules["api.db.services.llm_service"] = llm_service_mod

    tenant_model_service_mod = types.ModuleType("api.db.joint_services.tenant_model_service")

    def get_model_config_by_type_and_name(tenant_id, llm_type, name):
        llm_type_text = _llm_type_text(llm_type)
        model_name = str(name or "").strip()
        if llm_type_text == "embedding" and model_name.lower() in {"", "embedding", "default"}:
            try:
                from indexing_service.config import load_indexing_config

                model_name = load_indexing_config().models.embedding_model
            except Exception:
                pass
        elif model_name.lower() in {"", "chat", "default", "image2text", "ocr", "speech2text", "rerank", "tts"}:
            try:
                from indexing_service.config import load_indexing_config

                model_name = load_indexing_config().models.chat_model
            except Exception:
                pass
        return {"tenant_id": tenant_id, "llm_type": llm_type_text, "llm_name": model_name}

    def get_tenant_default_model_by_type(tenant_id, llm_type):
        return get_model_config_by_type_and_name(tenant_id, llm_type, _llm_type_text(llm_type))

    tenant_model_service_mod.get_model_config_by_type_and_name = get_model_config_by_type_and_name
    tenant_model_service_mod.get_tenant_default_model_by_type = get_tenant_default_model_by_type
    sys.modules["api.db.joint_services.tenant_model_service"] = tenant_model_service_mod

    tenant_llm_service_mod = types.ModuleType("api.db.services.tenant_llm_service")

    class TenantLLMService:
        @staticmethod
        def ensure_mineru_from_env(tenant_id):
            return None

        @staticmethod
        def ensure_opendataloader_from_env(tenant_id):
            return None

        @staticmethod
        def ensure_paddleocr_from_env(tenant_id):
            return None

        @staticmethod
        def query(*args, **kwargs):
            return []

    tenant_llm_service_mod.TenantLLMService = TenantLLMService
    sys.modules["api.db.services.tenant_llm_service"] = tenant_llm_service_mod

    knowledgebase_service_mod = types.ModuleType("api.db.services.knowledgebase_service")
    _kb_parser_configs: dict[str, dict[str, object]] = {}

    class _KnowledgebaseRecord:
        def __init__(self, kb_id: str, parser_config: dict[str, object]):
            self.id = kb_id
            self.parser_config = parser_config

    class KnowledgebaseService:
        @staticmethod
        def update_parser_config(kb_id, parser_config):
            merged = dict(_kb_parser_configs.get(kb_id, {}))
            merged.update(dict(parser_config or {}))
            _kb_parser_configs[str(kb_id)] = merged
            return True

        @staticmethod
        def get_by_id(kb_id):
            parser_config = _kb_parser_configs.get(str(kb_id))
            if parser_config is None:
                return False, None
            return True, _KnowledgebaseRecord(str(kb_id), dict(parser_config))

    knowledgebase_service_mod.KnowledgebaseService = KnowledgebaseService
    sys.modules["api.db.services.knowledgebase_service"] = knowledgebase_service_mod

    settings_mod = types.ModuleType("common.settings")
    settings_mod.PARALLEL_DEVICES = 0
    settings_mod.DOC_ENGINE = "elasticsearch"
    settings_mod.DOC_ENGINE_INFINITY = False
    settings_mod.DOC_ENGINE_OCEANBASE = False
    try:
        from indexing_service.config import load_indexing_config
        settings_mod.EMBEDDING_BATCH_SIZE = load_indexing_config().models.embedding_batch_size
    except Exception:
        settings_mod.EMBEDDING_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "16"))
    sys.modules["common.settings"] = settings_mod
    sys.modules["ragflow_runtime.common.settings"] = settings_mod
    setattr(sys.modules["common"], "settings", settings_mod)

    graphrag_pkg = sys.modules.get("rag.graphrag")
    if graphrag_pkg is None:
        graphrag_pkg = types.ModuleType("rag.graphrag")
        graphrag_pkg.__path__ = []
        sys.modules["rag.graphrag"] = graphrag_pkg

    graphrag_utils_mod = types.ModuleType("rag.graphrag.utils")
    _llm_cache: dict[str, str] = {}
    _tags_cache: dict[str, str] = {}

    class _Limiter:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def _cache_key(*parts):
        return sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()

    def get_llm_cache(llmnm, txt, history, genconf):
        return _llm_cache.get(_cache_key(llmnm, txt, history, genconf))

    def set_llm_cache(llmnm, txt, value, history, genconf):
        _llm_cache[_cache_key(llmnm, txt, history, genconf)] = str(value)

    def get_tags_from_cache(kb_ids):
        return _tags_cache.get(_cache_key(kb_ids))

    def set_tags_to_cache(kb_ids, tags):
        _tags_cache[_cache_key(kb_ids)] = json.dumps(tags, ensure_ascii=False)

    graphrag_utils_mod.chat_limiter = _Limiter()
    graphrag_utils_mod.get_llm_cache = get_llm_cache
    graphrag_utils_mod.set_llm_cache = set_llm_cache
    graphrag_utils_mod.get_tags_from_cache = get_tags_from_cache
    graphrag_utils_mod.set_tags_to_cache = set_tags_to_cache
    sys.modules["rag.graphrag.utils"] = graphrag_utils_mod


_install_compat_aliases()

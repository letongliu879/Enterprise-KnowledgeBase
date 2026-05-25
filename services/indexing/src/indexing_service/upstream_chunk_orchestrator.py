from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import random
import re
from dataclasses import dataclass, field

import ragflow_runtime
from api.db.joint_services.tenant_model_service import get_model_config_by_type_and_name
from api.db.services.llm_service import LLMBundle
from common import settings
from common.constants import LLMType, TAG_FLD
from common.metadata_utils import turn2jsonschema, update_metadata_to
from rag.graphrag.utils import chat_limiter, get_llm_cache, get_tags_from_cache, set_llm_cache, set_tags_to_cache
from rag.nlp import rag_tokenizer
from rag.prompts.generator import content_tagging, gen_metadata, keyword_extraction, question_proposal, run_toc_from_text
from indexing_service.vendor_table_es_metadata import aggregate_table_manual_doc_metadata


@dataclass
class UpstreamChunkPostprocessResult:
    chunks: list[dict[str, object]]
    document_metadata: dict[str, object] = field(default_factory=dict)
    outline: list[str] = field(default_factory=list)
    progress_events: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class UpstreamChunkOrchestrator:
    async def process(
        self,
        *,
        parser_id: str,
        parser_config: dict[str, object],
        chunks: list[dict[str, object]],
        tenant_id: str,
        language: str,
    ) -> UpstreamChunkPostprocessResult:
        docs = [dict(chunk) for chunk in chunks]
        progress_events: list[dict[str, object]] = []
        warnings: list[str] = []
        document_metadata: dict[str, object] = {}
        outline = _extract_outline(docs)

        if parser_config.get("auto_keywords", 0):
            progress_events.append({"progress": None, "message": "Start to generate keywords for every chunk ..."})
            try:
                await self._auto_keywords(docs, tenant_id=tenant_id, language=language, topn=int(parser_config["auto_keywords"]))
            except Exception as exc:  # pragma: no cover - runtime degradation path
                warnings.append(f"auto_keywords_failed:{type(exc).__name__}")

        if parser_config.get("auto_questions", 0):
            progress_events.append({"progress": None, "message": "Start to generate questions for every chunk ..."})
            try:
                await self._auto_questions(docs, tenant_id=tenant_id, language=language, topn=int(parser_config["auto_questions"]))
            except Exception as exc:  # pragma: no cover
                warnings.append(f"auto_questions_failed:{type(exc).__name__}")

        if parser_config.get("enable_metadata", False) and (
            parser_config.get("metadata") or parser_config.get("built_in_metadata")
        ):
            progress_events.append({"progress": None, "message": "Start to generate meta-data for every chunk ..."})
            try:
                generated = await self._auto_metadata(
                    docs,
                    tenant_id=tenant_id,
                    language=language,
                    parser_config=parser_config,
                )
                document_metadata = update_metadata_to(document_metadata, generated)
            except Exception as exc:  # pragma: no cover
                warnings.append(f"auto_metadata_failed:{type(exc).__name__}")
                fallback_metadata = _infer_document_metadata(
                    docs,
                    _metadata_schema(_merge_metadata_config(parser_config)),
                )
                if fallback_metadata:
                    document_metadata = update_metadata_to(document_metadata, fallback_metadata)

        if parser_config.get("tag_kb_ids"):
            progress_events.append({"progress": None, "message": "Start to tag for every chunk ..."})
            try:
                await self._content_tagging(
                    docs,
                    tenant_id=tenant_id,
                    language=language,
                    parser_config=parser_config,
                )
            except Exception as exc:  # pragma: no cover
                warnings.append(f"content_tagging_failed:{type(exc).__name__}")

        if parser_id.lower() == "naive" and parser_config.get("toc_extraction", False):
            progress_events.append({"progress": None, "message": "Start to generate table of content ..."})
            try:
                toc = await self._build_toc(docs, tenant_id=tenant_id, language=language)
                if toc:
                    document_metadata["outline"] = toc
                    outline = [str(item.get("title", "")).strip() for item in toc if str(item.get("title", "")).strip()]
            except Exception as exc:  # pragma: no cover
                warnings.append(f"toc_extraction_failed:{type(exc).__name__}")

        if parser_id.lower() == "table":
            try:
                aggregated = aggregate_table_manual_doc_metadata(
                    docs,
                    {
                        "parser_id": "table",
                        "parser_config": parser_config,
                        "kb_parser_config": parser_config,
                        "kb_id": "",
                    },
                )
                if aggregated:
                    document_metadata = update_metadata_to(document_metadata, aggregated)
            except Exception as exc:  # pragma: no cover
                warnings.append(f"table_doc_metadata_failed:{type(exc).__name__}")

        return UpstreamChunkPostprocessResult(
            chunks=docs,
            document_metadata=document_metadata,
            outline=outline,
            progress_events=progress_events,
            warnings=warnings,
        )

    async def _auto_keywords(self, docs: list[dict[str, object]], *, tenant_id: str, language: str, topn: int) -> None:
        chat_mdl = _chat_bundle(tenant_id=tenant_id, language=language)

        async def _one(doc: dict[str, object]) -> None:
            content = str(doc.get("content_with_weight", ""))
            cached = get_llm_cache(chat_mdl.llm_name, content, "keywords", {"topn": topn})
            if not cached:
                async with chat_limiter:
                    cached = await keyword_extraction(chat_mdl, content, topn)
                set_llm_cache(chat_mdl.llm_name, content, cached or "", "keywords", {"topn": topn})
            if cached:
                doc["important_kwd"] = [k for k in re.split(r"[,，;；、\r\n]+", str(cached)) if k.strip()]
                doc["important_tks"] = rag_tokenizer.tokenize(" ".join(doc["important_kwd"]))

        await asyncio.gather(*[_one(doc) for doc in docs], return_exceptions=False)

    async def _auto_questions(self, docs: list[dict[str, object]], *, tenant_id: str, language: str, topn: int) -> None:
        chat_mdl = _chat_bundle(tenant_id=tenant_id, language=language)

        async def _one(doc: dict[str, object]) -> None:
            content = str(doc.get("content_with_weight", ""))
            cached = get_llm_cache(chat_mdl.llm_name, content, "question", {"topn": topn})
            if not cached:
                async with chat_limiter:
                    cached = await question_proposal(chat_mdl, content, topn)
                set_llm_cache(chat_mdl.llm_name, content, cached or "", "question", {"topn": topn})
            if cached:
                doc["question_kwd"] = str(cached).split("\n")
                doc["question_tks"] = rag_tokenizer.tokenize("\n".join(doc["question_kwd"]))

        await asyncio.gather(*[_one(doc) for doc in docs], return_exceptions=False)

    async def _auto_metadata(
        self,
        docs: list[dict[str, object]],
        *,
        tenant_id: str,
        language: str,
        parser_config: dict[str, object],
    ) -> dict[str, object]:
        chat_mdl = _chat_bundle(tenant_id=tenant_id, language=language)
        metadata_conf = _merge_metadata_config(parser_config)

        async def _one(doc: dict[str, object]) -> None:
            content = str(doc.get("content_with_weight", ""))
            cached = get_llm_cache(chat_mdl.llm_name, content, "metadata", metadata_conf)
            if not cached:
                schema = _metadata_schema(metadata_conf)
                try:
                    async with chat_limiter:
                        cached = await gen_metadata(chat_mdl, schema, content)
                except Exception:
                    cached = ""
                set_llm_cache(chat_mdl.llm_name, content, cached or "{}", "metadata", metadata_conf)
            if cached:
                doc["metadata_obj"] = cached
            if not doc.get("metadata_obj"):
                doc["metadata_obj"] = _infer_metadata_from_doc(doc, _metadata_schema(metadata_conf))

        await asyncio.gather(*[_one(doc) for doc in docs], return_exceptions=False)
        metadata: dict[str, object] = {}
        for doc in docs:
            doc_meta = doc.pop("metadata_obj", None)
            metadata = update_metadata_to(metadata, doc_meta)
        inferred_metadata = _infer_document_metadata(docs, _metadata_schema(metadata_conf))
        if not metadata:
            metadata = inferred_metadata
        else:
            metadata = _merge_missing_metadata(metadata, inferred_metadata)
        return metadata

    async def _content_tagging(
        self,
        docs: list[dict[str, object]],
        *,
        tenant_id: str,
        language: str,
        parser_config: dict[str, object],
    ) -> None:
        kb_ids = parser_config.get("tag_kb_ids", [])
        topn_tags = int(parser_config.get("topn_tags", 3))
        all_tags = get_tags_from_cache(kb_ids)
        if all_tags:
            all_tags = _normalize_all_tags(json.loads(all_tags))
        else:
            all_tags = _normalize_all_tags(parser_config.get("available_tags") or [])
            set_tags_to_cache(kb_ids, all_tags)
        if not all_tags:
            return
        chat_mdl = _chat_bundle(tenant_id=tenant_id, language=language)
        examples = []
        docs_to_tag = []
        for doc in docs:
            if doc.get(TAG_FLD):
                inferred = _infer_tags_from_content(str(doc.get("content_with_weight", "")), all_tags, topn_tags=topn_tags)
                if inferred:
                    merged_tags = dict(doc.get(TAG_FLD) or {})
                    for key, value in inferred.items():
                        merged_tags.setdefault(key, value)
                    doc[TAG_FLD] = merged_tags
                examples.append({"content": doc["content_with_weight"], TAG_FLD: doc[TAG_FLD]})
                continue
            if _tag_via_retriever(
                tenant_id=tenant_id,
                kb_ids=kb_ids,
                doc=doc,
                all_tags=all_tags,
                topn_tags=topn_tags,
            ):
                inferred = _infer_tags_from_content(str(doc.get("content_with_weight", "")), all_tags, topn_tags=topn_tags)
                if inferred:
                    merged_tags = dict(doc.get(TAG_FLD) or {})
                    for key, value in inferred.items():
                        merged_tags.setdefault(key, value)
                    doc[TAG_FLD] = merged_tags
                examples.append({"content": doc["content_with_weight"], TAG_FLD: doc[TAG_FLD]})
                continue
            docs_to_tag.append(doc)

        async def _one(doc: dict[str, object]) -> None:
            content = str(doc.get("content_with_weight", ""))
            cached = get_llm_cache(chat_mdl.llm_name, content, all_tags, {"topn": topn_tags})
            if not cached:
                seed_examples = (
                    random.choices(examples, k=2)
                    if len(examples) > 2
                    else list(examples)
                ) or [{"content": "This is an example", TAG_FLD: {"example": 1}}]
                try:
                    async with chat_limiter:
                        cached_obj = await content_tagging(chat_mdl, content, all_tags, seed_examples[:2], topn_tags)
                except Exception:
                    cached_obj = _infer_tags_from_content(content, all_tags, topn_tags=topn_tags)
                if not cached_obj:
                    cached_obj = _infer_tags_from_content(content, all_tags, topn_tags=topn_tags)
                if cached_obj:
                    cached = json.dumps(cached_obj, ensure_ascii=False)
            if cached:
                set_llm_cache(chat_mdl.llm_name, content, cached, all_tags, {"topn": topn_tags})
                doc[TAG_FLD] = json.loads(cached)
            inferred = _infer_tags_from_content(content, all_tags, topn_tags=topn_tags)
            if inferred:
                merged_tags = dict(doc.get(TAG_FLD) or {})
                for key, value in inferred.items():
                    merged_tags.setdefault(key, value)
                doc[TAG_FLD] = merged_tags

        await asyncio.gather(*[_one(doc) for doc in docs_to_tag], return_exceptions=False)

    async def _build_toc(self, docs: list[dict[str, object]], *, tenant_id: str, language: str) -> list[dict[str, object]]:
        chat_mdl = _chat_bundle(tenant_id=tenant_id, language=language)
        ordered = sorted(
            docs,
            key=lambda doc: (
                doc.get("page_num_int", [0])[0] if isinstance(doc.get("page_num_int"), list) and doc.get("page_num_int") else 0,
                doc.get("top_int", [0])[0] if isinstance(doc.get("top_int"), list) and doc.get("top_int") else 0,
            ),
        )
        toc = await run_toc_from_text([str(doc.get("content_with_weight", "")) for doc in ordered], chat_mdl, _progress_noop)
        if toc:
            return toc
        return _infer_toc_from_docs(ordered)


def _chat_bundle(*, tenant_id: str, language: str) -> LLMBundle:
    model_config = get_model_config_by_type_and_name(tenant_id, LLMType.CHAT, "chat")
    return LLMBundle(tenant_id, model_config, lang=language)


def _extract_outline(chunks: list[dict[str, object]]) -> list[str]:
    if chunks and chunks[0].get("__outline__"):
        return [
            str(item.get("title", "")).strip()
            for item in chunks[0].get("__outline__", [])
            if str(item.get("title", "")).strip()
        ]
    return []


def _progress_noop(prog=None, msg=""):
    return None


def _merge_metadata_config(parser_config: dict[str, object]) -> object:
    metadata_conf = parser_config.get("metadata", [])
    built_in_metadata = list(parser_config.get("built_in_metadata") or [])
    if isinstance(metadata_conf, list):
        metadata_conf = [
            {"key": item, "type": "string", "description": item}
            if isinstance(item, str)
            else item
            for item in metadata_conf
        ]
    built_in_metadata = [
        {"key": item, "type": "string", "description": item}
        if isinstance(item, str)
        else item
        for item in built_in_metadata
    ]
    if isinstance(metadata_conf, dict):
        if not isinstance(metadata_conf.get("properties"), dict):
            metadata_conf = {"type": "object", "properties": {}}
        if built_in_metadata:
            metadata_conf = {
                **metadata_conf,
                "properties": {
                    **metadata_conf.get("properties", {}),
                    **turn2jsonschema(built_in_metadata).get("properties", {}),
                },
            }
    elif isinstance(metadata_conf, list):
        metadata_conf = metadata_conf + built_in_metadata
    else:
        metadata_conf = built_in_metadata
    return metadata_conf


def _metadata_schema(metadata_conf) -> dict[str, object]:
    if isinstance(metadata_conf, dict) and isinstance(metadata_conf.get("properties"), dict):
        return metadata_conf
    return turn2jsonschema(_normalize_metadata_items(metadata_conf))


def _normalize_metadata_items(metadata_conf: object) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for item in metadata_conf or []:
        if isinstance(item, str):
            key = item.strip()
            if not key:
                continue
            normalized.append({"key": key, "description": key})
            continue
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or item.get("name") or "").strip()
        if not key:
            continue
        normalized_item: dict[str, object] = {
            "key": key,
            "description": str(item.get("description") or key),
        }
        enum_values = item.get("enum")
        if isinstance(enum_values, list) and enum_values:
            normalized_item["enum"] = enum_values
        normalized.append(normalized_item)
    return normalized


def _normalize_all_tags(all_tags: object) -> dict[str, float]:
    if isinstance(all_tags, dict):
        normalized: dict[str, float] = {}
        for key, value in all_tags.items():
            key_text = str(key).strip()
            if not key_text:
                continue
            try:
                normalized[key_text] = float(value)
            except (TypeError, ValueError):
                normalized[key_text] = 1.0
        return normalized
    if isinstance(all_tags, list):
        return {
            str(item).strip(): 1.0
            for item in all_tags
            if str(item).strip()
        }
    return {}


def _tag_via_retriever(
    *,
    tenant_id: str,
    kb_ids: object,
    doc: dict[str, object],
    all_tags: dict[str, float],
    topn_tags: int,
) -> bool:
    retriever = getattr(settings, "retriever", None)
    if retriever is None or not kb_ids:
        return False
    prepared_doc = dict(doc)
    if not prepared_doc.get("title_tks"):
        prepared_doc["title_tks"] = rag_tokenizer.tokenize(_doc_title(doc))
    if not prepared_doc.get("content_ltks"):
        prepared_doc["content_ltks"] = rag_tokenizer.tokenize(str(doc.get("content_with_weight", "")))
    try:
        tagged = bool(
            retriever.tag_content(
                tenant_id,
                list(kb_ids),
                prepared_doc,
                all_tags,
                topn_tags=topn_tags,
                S=1000,
            )
        )
    except Exception as exc:  # pragma: no cover - optional host capability
        logging.debug("retriever tag_content unavailable: %s", exc)
        return False
    if tagged and prepared_doc.get(TAG_FLD):
        doc[TAG_FLD] = prepared_doc[TAG_FLD]
        return True
    return False


def _infer_tags_from_content(content: str, all_tags, *, topn_tags: int) -> dict[str, int]:
    normalized = str(content).lower()
    inferred: dict[str, int] = {}
    for tag in all_tags:
        tag_text = str(tag).strip()
        if not tag_text:
            continue
        tag_norm = tag_text.lower()
        tag_tokens = [token for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", tag_norm) if token]
        if tag_norm in normalized:
            inferred[tag_text] = 1
        elif tag_tokens and all(token in normalized for token in tag_tokens):
            inferred[tag_text] = 1
        if len(inferred) >= max(topn_tags, 1):
            break
    return inferred


def _infer_metadata_from_doc(doc: dict[str, object], schema: dict[str, object]) -> dict[str, object]:
    properties = schema.get("properties", {})
    inferred: dict[str, object] = {}
    content = str(doc.get("content_with_weight", ""))
    title = _doc_title(doc)
    doc_type = _infer_doc_type(doc, content)
    department = _infer_department(content)
    for key in properties:
        key_norm = str(key).strip().lower()
        if key_norm == "title":
            inferred[key] = title
        elif key_norm in {"doc_type", "document_type", "type"}:
            inferred[key] = doc_type
        elif key_norm in {"department", "dept"} and department:
            inferred[key] = department
        elif key_norm in {"filename", "document_name"} and doc.get("docnm_kwd"):
            inferred[key] = str(doc.get("docnm_kwd"))
        elif key_norm in {"summary", "abstract"}:
            inferred[key] = _summary_text(content)
    return {key: value for key, value in inferred.items() if value not in (None, "", [], {})}


def _infer_document_metadata(docs: list[dict[str, object]], schema: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for doc in docs:
        merged = update_metadata_to(merged, _infer_metadata_from_doc(doc, schema))
    return merged


def _merge_missing_metadata(metadata: dict[str, object], inferred: dict[str, object]) -> dict[str, object]:
    merged = dict(metadata)
    for key, value in inferred.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value
    return merged


def _infer_toc_from_docs(docs: list[dict[str, object]]) -> list[dict[str, object]]:
    toc: list[dict[str, object]] = []
    for index, doc in enumerate(docs):
        content = str(doc.get("content_with_weight", ""))
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
            else:
                match = re.match(r"^(?:Q|Question)[:：]\s*(.+)$", stripped, re.IGNORECASE)
                if match:
                    title = match.group(1).strip()
                else:
                    match = re.match(r"^\d+(?:\.\d+)*[.)]?\s+(.+)$", stripped)
                    if not match:
                        continue
                    title = match.group(1).strip()
            if title:
                toc.append({"level": "0", "title": title, "chunk_id": index})
        if toc:
            continue
    if toc:
        return toc
    fallback_title = _doc_title(docs[0]) if docs else "Document"
    return [{"level": "0", "title": fallback_title, "chunk_id": 0}] if fallback_title else []


def _doc_title(doc: dict[str, object]) -> str:
    raw = str(doc.get("docnm_kwd", "")).strip()
    if raw:
        return Path(raw).stem.strip() or raw
    title_tks = str(doc.get("title_tks", "")).strip()
    if title_tks:
        return title_tks.replace(" - ", " ").strip()
    return "Document"


def _infer_doc_type(doc: dict[str, object], content: str) -> str:
    lowered = content.lower()
    if re.search(r"(^|\n)\s*q[:：]\s*", content, re.IGNORECASE) and re.search(r"(^|\n)\s*a[:：]\s*", content, re.IGNORECASE):
        return "qa"
    if any(str(key).endswith("_raw") or str(key).endswith("_tks") for key in doc.keys()):
        return "table"
    if content.count("#") >= 2:
        return "manual"
    if "slide" in lowered or "ppt" in str(doc.get("docnm_kwd", "")).lower():
        return "presentation"
    return "text"


def _infer_department(content: str) -> str | None:
    lowered = content.lower()
    mapping = {
        "finance": ["finance", "reimbursement", "expense", "invoice", "budget"],
        "hr": ["human resources", "hr", "recruitment", "employee"],
        "legal": ["legal", "contract", "compliance", "law"],
        "it": ["it", "system", "software", "security", "network"],
    }
    for department, keywords in mapping.items():
        for keyword in keywords:
            if " " in keyword:
                if keyword in lowered:
                    return department
            elif re.search(rf"\b{re.escape(keyword)}\b", lowered):
                return department
    return None


def _summary_text(content: str) -> str:
    text = re.sub(r"\s+", " ", content).strip()
    if not text:
        return ""
    if len(text) <= 160:
        return text
    return text[:157].rstrip() + "..."

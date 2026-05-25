from __future__ import annotations

import re


class VectorTextBuilder:
    def build(
        self,
        *,
        title: str,
        display_text: str,
        upstream_chunk: dict[str, object] | None = None,
    ) -> str:
        chunk = upstream_chunk or {}
        question_lines = chunk.get("question_kwd")
        if isinstance(question_lines, list):
            question_text = "\n".join(str(item).strip() for item in question_lines if str(item).strip()).strip()
            if question_text:
                return _normalize_for_embedding(question_text)
        text = display_text.strip()
        if not text:
            text = "None"
        return _normalize_for_embedding(text)

    def build_title_text(
        self,
        *,
        title: str,
        filename: str | None = None,
        upstream_chunk: dict[str, object] | None = None,
    ) -> str:
        chunk = upstream_chunk or {}
        doc_name = str(chunk.get("docnm_kwd") or "").strip()
        if doc_name:
            return doc_name
        if filename and filename.strip():
            return filename.strip()
        if title.strip():
            return title.strip()
        return "Title"

    def title_weight(self, *, parser_config: dict[str, object] | None = None) -> float:
        config = parser_config or {}
        raw_weight = config.get("filename_embd_weight", 0.1)
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            weight = 0.1
        if not weight:
            weight = 0.1
        return max(0.0, min(weight, 1.0))


def _normalize_for_embedding(text: str) -> str:
    normalized = re.sub(r"</?(table|td|caption|tr|th)( [^<>]{0,12})?>", " ", text)
    normalized = normalized.strip()
    if not normalized:
        return "None"
    return normalized

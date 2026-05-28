from __future__ import annotations

import re


class VectorTextBuilder:
    def build(
        self,
        *,
        title: str,
        display_text: str,
        upstream_chunk: dict[str, object] | None = None,
        embedding_text_policy: str = "display_text",
        section_path: list[str] | str = "",
    ) -> str:
        chunk = upstream_chunk or {}

        if embedding_text_policy == "question_kwd":
            question_lines = chunk.get("question_kwd")
            if isinstance(question_lines, list):
                question_text = "\n".join(str(item).strip() for item in question_lines if str(item).strip()).strip()
                if question_text:
                    return _normalize_for_embedding(question_text)

        elif embedding_text_policy == "display_text_with_authors":
            authors_lines = chunk.get("authors") or chunk.get("authors_kwd") or chunk.get("author")
            if isinstance(authors_lines, list):
                authors_text = "\n".join(str(item).strip() for item in authors_lines if str(item).strip()).strip()
            elif isinstance(authors_lines, str):
                authors_text = authors_lines.strip()
            else:
                authors_text = ""
            if authors_text:
                combined = f"{display_text.strip()}\n\nAuthors: {authors_text}"
                return _normalize_for_embedding(combined)

        elif embedding_text_policy == "display_text_with_section_path":
            if isinstance(section_path, list):
                path_text = " > ".join(str(p).strip() for p in section_path if str(p).strip())
            else:
                path_text = str(section_path).strip()
            if path_text:
                combined = f"{path_text}\n{display_text.strip()}"
                return _normalize_for_embedding(combined)

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

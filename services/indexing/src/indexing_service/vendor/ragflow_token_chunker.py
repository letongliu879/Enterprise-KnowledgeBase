from __future__ import annotations

#
# Source-anchored port of the pure JSON chunk assembly helpers from
# RAGFlow rag/flow/chunker/token_chunker.py under Apache 2.0.
# This intentionally excludes ProcessBase/runtime plumbing and keeps the
# chunk assembly stages reusable from services/indexing.
#

from copy import deepcopy
import re

from indexing_service.vendor.ragflow_pdf_chunk_metadata import (
    PDF_POSITIONS_KEY,
    extract_pdf_positions,
    finalize_pdf_chunk,
    merge_pdf_positions,
)


def num_tokens_from_string(text: str) -> int:
    if not text or not text.strip():
        return 0
    return len([term for term in re.split(r"\s+", text.strip()) if term])


def normalize_overlapped_percent(value: float | int | None) -> float:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        return 0
    if numeric < 0:
        return 0
    if numeric >= 1:
        return 0.99
    return numeric


def naive_merge(payload: str, chunk_token_size: int, _separator: str, overlapped_percent: float) -> list[str]:
    words = [word for word in re.split(r"(\s+)", payload or "") if word]
    if not words:
        return []

    chunks: list[str] = []
    current = ""
    current_tokens = 0
    budget = max(int(chunk_token_size), 1)
    for token in words:
        proposed = current + token
        token_count = num_tokens_from_string(proposed)
        if current and token_count > budget:
            chunks.append(current.strip())
            if overlapped_percent > 0:
                overlap_chars = int(len(current) * overlapped_percent)
                current = current[-overlap_chars:] + token
            else:
                current = token
            current_tokens = num_tokens_from_string(current)
            continue
        current = proposed
        current_tokens = token_count

    if current.strip() and current_tokens > 0:
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk.strip()]


def compile_delimiter_pattern(delimiters: list[str] | None) -> str:
    raw_delimiters = "".join(delimiter for delimiter in (delimiters or []) if delimiter)
    custom_delimiters = [match.group(1) for match in re.finditer(r"`([^`]+)`", raw_delimiters)]
    if not custom_delimiters:
        return ""
    return "|".join(re.escape(text) for text in sorted(set(custom_delimiters), key=len, reverse=True))


def split_text_by_pattern(text: str, pattern: str) -> list[str]:
    if not pattern:
        return [text or ""]

    split_texts = re.split(r"(%s)" % pattern, text or "", flags=re.DOTALL)
    chunks: list[str] = []
    for index in range(0, len(split_texts), 2):
        chunk = split_texts[index]
        if not chunk:
            continue
        if index + 1 < len(split_texts):
            chunk += split_texts[index + 1]
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def build_json_chunks(json_result: list[dict[str, object]], delimiter_pattern: str) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    for item in json_result:
        doc_type = str(item.get("doc_type_kwd") or "").strip().lower()
        if doc_type == "table":
            ck_type = "table"
        elif doc_type == "image":
            ck_type = "image"
        else:
            ck_type = "text"

        text = item.get("text")
        if not isinstance(text, str):
            text = item.get("content_with_weight")
        if not isinstance(text, str):
            text = ""

        preview_positions = extract_pdf_positions(item)
        img_id = item.get("img_id")

        if ck_type == "text":
            text_segments = split_text_by_pattern(text, delimiter_pattern) if delimiter_pattern else [text]
            for segment in text_segments:
                if not segment or not segment.strip():
                    continue
                chunks.append(
                    {
                        "text": segment,
                        "doc_type_kwd": "text",
                        "ck_type": "text",
                        PDF_POSITIONS_KEY: deepcopy(preview_positions),
                        "tk_nums": num_tokens_from_string(segment),
                    }
                )
            continue

        chunks.append(
            {
                "text": text or "",
                "doc_type_kwd": ck_type,
                "ck_type": ck_type,
                "img_id": img_id,
                PDF_POSITIONS_KEY: deepcopy(preview_positions),
                "tk_nums": num_tokens_from_string(text or ""),
                "context_above": "",
                "context_below": "",
            }
        )

    return chunks


def merge_text_chunks_by_token_size(
    chunks: list[dict[str, object]],
    chunk_token_size: int,
    overlapped_percent: float,
) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    prev_text_idx = -1
    threshold = chunk_token_size * (1 - normalize_overlapped_percent(overlapped_percent))

    for chunk in chunks:
        if chunk["ck_type"] != "text":
            merged.append(deepcopy(chunk))
            prev_text_idx = -1
            continue

        current = deepcopy(chunk)
        should_start_new = prev_text_idx < 0 or int(merged[prev_text_idx]["tk_nums"]) > threshold
        if should_start_new:
            if prev_text_idx >= 0 and overlapped_percent > 0 and str(merged[prev_text_idx]["text"]):
                overlapped = str(merged[prev_text_idx]["text"])
                overlap_start = int(len(overlapped) * (1 - normalize_overlapped_percent(overlapped_percent)))
                current["text"] = overlapped[overlap_start:] + str(current["text"])
                current["tk_nums"] = num_tokens_from_string(str(current["text"]))
            merged.append(current)
            prev_text_idx = len(merged) - 1
            continue

        if str(merged[prev_text_idx]["text"]) and str(current["text"]):
            merged[prev_text_idx]["text"] = f"{merged[prev_text_idx]['text']}\n{current['text']}"
        else:
            merged[prev_text_idx]["text"] = f"{merged[prev_text_idx]['text']}{current['text']}"
        merged[prev_text_idx][PDF_POSITIONS_KEY].extend(current.get(PDF_POSITIONS_KEY) or [])
        merged[prev_text_idx]["tk_nums"] = int(merged[prev_text_idx]["tk_nums"]) + int(current["tk_nums"])

    return merged


def split_chunk_docs_by_children(chunks: list[dict[str, object]], pattern: str) -> list[dict[str, object]]:
    if not pattern:
        return chunks

    docs: list[dict[str, object]] = []
    for chunk in chunks:
        if chunk.get("doc_type_kwd", "text") != "text":
            docs.append(chunk)
            continue

        split_texts = split_text_by_pattern(str(chunk.get("text", "")), pattern)
        mom = str(chunk.get("mom") or chunk.get("text", ""))
        for text in split_texts:
            if not text.strip():
                continue
            child = deepcopy(chunk)
            child["mom"] = mom
            child["text"] = text
            docs.append(child)

    return docs


def finalize_json_chunks(chunks: list[dict[str, object]]) -> list[dict[str, object]]:
    docs: list[dict[str, object]] = []
    for chunk in chunks:
        text = f"{chunk.get('context_above') or ''}{chunk.get('text') or ''}{chunk.get('context_below') or ''}"
        if not text.strip():
            continue

        doc: dict[str, object] = {
            "text": text,
            "doc_type_kwd": chunk.get("doc_type_kwd", "text"),
        }
        if chunk.get(PDF_POSITIONS_KEY):
            doc[PDF_POSITIONS_KEY] = deepcopy(chunk[PDF_POSITIONS_KEY])
        if chunk.get("mom"):
            doc["mom"] = chunk["mom"]
        if chunk.get("img_id"):
            doc["img_id"] = chunk["img_id"]
        if chunk.get("source_block_ids"):
            doc["source_block_ids"] = deepcopy(chunk["source_block_ids"])
        if chunk.get("section_path"):
            doc["section_path"] = deepcopy(chunk["section_path"])
        if chunk.get("section_paths"):
            doc["section_paths"] = deepcopy(chunk["section_paths"])
        if chunk.get("source_line_from") is not None:
            doc["source_line_from"] = chunk["source_line_from"]
        if chunk.get("source_line_to") is not None:
            doc["source_line_to"] = chunk["source_line_to"]
        docs.append(finalize_pdf_chunk(doc))

    return docs


def assemble_text_chunks(
    sections: list[dict[str, object]],
    *,
    delimiter_mode: str = "token_size",
    chunk_token_size: int = 512,
    delimiters: list[str] | None = None,
    overlapped_percent: float = 0,
    children_delimiters: list[str] | None = None,
) -> list[dict[str, object]]:
    if delimiter_mode == "one":
        non_empty_sections = [
            item
            for item in sections
            if str(item.get("text") or item.get("content_with_weight") or "").strip()
        ]
        merged_text = "\n".join(
            str(item.get("text") or item.get("content_with_weight") or "")
            for item in non_empty_sections
        )
        if not merged_text.strip():
            return []
        return [{"text": merged_text}]

    delimiter_pattern = compile_delimiter_pattern(delimiters or [])
    chunks = build_json_chunks(sections, delimiter_pattern)
    if not delimiter_pattern:
        chunks = merge_text_chunks_by_token_size(chunks, chunk_token_size, overlapped_percent)

    custom_pattern = "|".join(
        re.escape(text)
        for text in sorted(set(children_delimiters or []), key=len, reverse=True)
        if text
    )
    if custom_pattern:
        chunks = split_chunk_docs_by_children(chunks, custom_pattern)

    return finalize_json_chunks(chunks)

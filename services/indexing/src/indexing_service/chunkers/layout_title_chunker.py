from __future__ import annotations

from dataclasses import dataclass
import re

from indexing_service.vendor.ragflow_title_chunker.common import (
    BODY_LEVEL,
    DEFAULT_LEVEL_GROUPS,
    resolve_frequency_levels,
    resolve_target_level,
)
from indexing_service.vendor.ragflow_title_chunker.group_chunker import group_record_groups
from indexing_service.vendor.ragflow_title_chunker.hierarchy_chunker import hierarchy_record_groups


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


@dataclass(frozen=True)
class ChunkDraft:
    section_path: list[str]
    display_text: str
    source_block_ids: list[str]
    source_line_from: int
    source_line_to: int
    parent_context: str | None = None


@dataclass(frozen=True)
class _LineRecord:
    line_no: int
    text: str
    kind: str
    heading_level: int | None = None
    heading_path: list[str] | None = None
    raw_text: str | None = None


@dataclass(frozen=True)
class _SectionBlock:
    text: str
    line_from: int
    line_to: int
    heading_path: list[str]


class LayoutTitleChunker:
    """Adapter over vendorized RAGFlow-style title chunking semantics."""

    def __init__(
        self,
        *,
        hierarchy_depth: int = 2,
        use_hierarchy: bool = False,
        include_heading_content: bool = False,
        root_chunk_as_heading: bool = False,
        levels: list[list[str]] | None = None,
    ) -> None:
        self._hierarchy_depth = hierarchy_depth
        self._use_hierarchy = use_hierarchy
        self._include_heading_content = include_heading_content
        self._root_chunk_as_heading = root_chunk_as_heading
        self._levels = levels or DEFAULT_LEVEL_GROUPS

    def chunk(self, markdown_text: str, *, fallback_title: str) -> list[ChunkDraft]:
        records = self._extract_line_records(markdown_text)
        if not records:
            return []

        vendor_records = [self._to_vendor_record(record) for record in records if record.kind != "blank"]
        resolved = resolve_frequency_levels(vendor_records, self._levels)
        title_levels = [int(level) for level in resolved["levels"]]
        vendor_records = self._apply_resolved_heading_paths(vendor_records, title_levels, fallback_title)
        grouped_records = (
            hierarchy_record_groups(
                vendor_records,
                title_levels,
                hierarchy=self._hierarchy_depth,
                include_heading_content=self._include_heading_content,
            )
            if self._use_hierarchy
            else group_record_groups(
                vendor_records,
                title_levels,
                target_level=(resolve_target_level(title_levels, self._hierarchy_depth) if title_levels else None),
            )
        )

        chunk_drafts: list[ChunkDraft] = []
        for group in grouped_records:
            drafts = self.assemble_vendor_group(group, fallback_title=fallback_title)
            for draft in drafts:
                chunk_drafts.append(draft)

        if self._root_chunk_as_heading and len(chunk_drafts) > 1:
            root_text = chunk_drafts[0].display_text
            return [
                ChunkDraft(
                    section_path=draft.section_path,
                    display_text=f"{root_text}\n{draft.display_text}".strip(),
                    source_block_ids=draft.source_block_ids,
                    source_line_from=draft.source_line_from,
                    source_line_to=draft.source_line_to,
                    parent_context=draft.parent_context,
                )
                for draft in chunk_drafts[1:]
            ]
        return chunk_drafts

    def _to_vendor_record(self, record: _LineRecord) -> dict[str, object]:
        text = record.text.strip()
        if record.kind == "heading" and record.heading_level is not None:
            text = (record.raw_text or f"{'#' * record.heading_level} {text}").strip()
        return {
            "text": text,
            "line_no": record.line_no,
            "kind": record.kind,
            "doc_type_kwd": "text",
            "layout": "heading" if record.kind == "heading" else "",
            "heading_level": record.heading_level,
            "level": BODY_LEVEL,
            "heading_path": [],
        }

    def _apply_resolved_heading_paths(
        self,
        vendor_records: list[dict[str, object]],
        title_levels: list[int],
        fallback_title: str,
    ) -> list[dict[str, object]]:
        stack: list[str] = []
        annotated: list[dict[str, object]] = []
        for record, level in zip(vendor_records, title_levels):
            normalized = dict(record)
            normalized["level"] = level
            heading_text = self._normalize_heading_text(str(record["text"]))
            if level < BODY_LEVEL and heading_text:
                while len(stack) >= level:
                    stack.pop()
                stack.append(heading_text)
                normalized["heading_path"] = [*stack]
            else:
                normalized["heading_path"] = [*stack] if stack else [fallback_title]
            annotated.append(normalized)
        return annotated

    @staticmethod
    def _normalize_heading_text(text: str) -> str:
        heading = HEADING_PATTERN.match(text.strip())
        if heading is not None:
            return heading.group(2).strip()
        return text.strip()

    def assemble_vendor_group(
        self,
        group: list[dict[str, object]],
        *,
        fallback_title: str,
    ) -> list[ChunkDraft]:
        section_path = self._resolve_section_path(group, fallback_title)
        body_records = [record for record in group if int(record["level"]) == BODY_LEVEL]
        body_blocks = [
            _SectionBlock(
                text=str(record["text"]),
                line_from=int(record["line_no"]),
                line_to=int(record["line_no"]),
                heading_path=section_path,
            )
            for record in body_records
            if str(record["text"]).strip()
        ]
        if not body_blocks:
            body_blocks = [
                _SectionBlock(
                    text="\n".join(section_path).strip(),
                    line_from=int(group[0]["line_no"]),
                    line_to=int(group[-1]["line_no"]),
                    heading_path=section_path,
                )
            ]
        return [
            ChunkDraft(
                section_path=section_path,
                display_text="\n\n".join(block.text for block in body_blocks),
                source_block_ids=[f"blk_{block.line_from:04d}_{block.line_to:04d}" for block in body_blocks],
                source_line_from=body_blocks[0].line_from,
                source_line_to=body_blocks[-1].line_to,
                parent_context=None,
            )
        ]

    def _resolve_section_path(self, group: list[dict[str, object]], fallback_title: str) -> list[str]:
        heading_paths = [
            [str(part).strip() for part in record.get("heading_path", []) if str(part).strip()]
            for record in group
            if int(record["level"]) < BODY_LEVEL
        ]
        heading_paths = [path for path in heading_paths if path]
        if not heading_paths:
            return [fallback_title]
        return max(heading_paths, key=len)

    def _extract_line_records(self, markdown_text: str) -> list[_LineRecord]:
        records: list[_LineRecord] = []
        for line_no, raw_line in enumerate(markdown_text.splitlines(), start=1):
            stripped = raw_line.strip()
            if not stripped:
                records.append(_LineRecord(line_no=line_no, text="", kind="blank"))
                continue
            heading = HEADING_PATTERN.match(stripped)
            if heading is not None:
                records.append(
                    _LineRecord(
                        line_no=line_no,
                        text=heading.group(2).strip(),
                        kind="heading",
                        heading_level=len(heading.group(1)),
                        raw_text=stripped,
                    )
                )
                continue
            records.append(_LineRecord(line_no=line_no, text=stripped, kind="body", raw_text=stripped))
        return records

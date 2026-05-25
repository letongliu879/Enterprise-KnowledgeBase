from __future__ import annotations

#
# Source-anchored port of selected pure metadata helpers from
# RAGFlow rag/flow/parser/pdf_chunk_metadata.py under Apache 2.0.
# This keeps only the coordinate normalization/finalization logic that
# services/indexing can consume without pulling in the upstream runtime.
#

from copy import deepcopy


PDF_POSITIONS_KEY = "_pdf_positions"


def _extract_raw_positions(item: dict[str, object]) -> list[list[object]]:
    positions = item.get(PDF_POSITIONS_KEY)
    if isinstance(positions, list):
        return deepcopy(positions)

    positions = item.get("positions")
    if isinstance(positions, list):
        return deepcopy(positions)

    position_int = item.get("position_int")
    if isinstance(position_int, list):
        return [
            list(pos)
            for pos in position_int
            if isinstance(pos, (list, tuple)) and len(pos) >= 5
        ]

    if item.get("page_number") is not None and all(
        item.get(key) is not None for key in ["x0", "x1", "top", "bottom"]
    ):
        return [[item["page_number"], item["x0"], item["x1"], item["top"], item["bottom"]]]

    return []


def extract_pdf_positions(item: dict[str, object] | object) -> list[list[float]]:
    if not isinstance(item, dict):
        return []

    positions = _extract_raw_positions(item)
    ref_page_number = item.get("page_number")
    ref_page_number = int(ref_page_number) if isinstance(ref_page_number, (int, float)) else None
    if ref_page_number is not None and ref_page_number <= 0:
        ref_page_number += 1

    normalized_positions: list[list[float]] = []
    for pos in positions:
        if not isinstance(pos, (list, tuple)) or len(pos) < 5:
            continue

        page_number = pos[0][-1] if isinstance(pos[0], list) else pos[0]
        try:
            page_number = int(page_number)
            if ref_page_number is not None and page_number == ref_page_number - 1:
                page_number = ref_page_number
            elif page_number <= 0:
                page_number += 1

            normalized_positions.append(
                [page_number, float(pos[1]), float(pos[2]), float(pos[3]), float(pos[4])]
            )
        except (TypeError, ValueError):
            continue

    return normalized_positions


def merge_pdf_positions(sources: list[dict[str, object] | list[object]] | None) -> list[list[float]]:
    merged: list[list[float]] = []
    seen: set[tuple[float, ...]] = set()
    for source in sources or []:
        if isinstance(source, dict):
            positions = extract_pdf_positions(source)
        elif isinstance(source, list):
            positions = source
        else:
            positions = []

        for pos in positions:
            if not isinstance(pos, (list, tuple)) or len(pos) < 5:
                continue
            key = tuple(pos[:5])
            if key in seen:
                continue
            seen.add(key)
            merged.append(list(pos[:5]))

    merged.sort(key=lambda item: (item[0], item[3], item[1]))
    return merged


def build_pdf_position_fields(positions: list[list[float]] | list[tuple[float, ...]]) -> dict[str, list[tuple[int, ...]] | list[int]]:
    position_int: list[tuple[int, int, int, int, int]] = []
    page_num_int: list[int] = []
    top_int: list[int] = []
    for pos in positions or []:
        if not isinstance(pos, (list, tuple)) or len(pos) < 5:
            continue
        try:
            page_no = int(pos[0])
            left = int(pos[1])
            right = int(pos[2])
            top = int(pos[3])
            bottom = int(pos[4])
        except (TypeError, ValueError):
            continue

        position_int.append((page_no, left, right, top, bottom))
        page_num_int.append(page_no)
        top_int.append(top)

    return {
        "position_int": deepcopy(position_int),
        "page_num_int": deepcopy(page_num_int),
        "top_int": deepcopy(top_int),
    }


def finalize_pdf_chunk(chunk: dict[str, object] | object) -> dict[str, object] | object:
    if not isinstance(chunk, dict):
        return chunk

    positions = extract_pdf_positions(chunk)
    if positions:
        chunk.update(build_pdf_position_fields(positions))
    chunk.pop(PDF_POSITIONS_KEY, None)
    return chunk

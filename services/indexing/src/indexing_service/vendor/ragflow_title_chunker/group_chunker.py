from __future__ import annotations

#
# Adapted from RAGFlow title_chunker/group_chunker.py under Apache 2.0.
#

from indexing_service.vendor.ragflow_title_chunker.common import BODY_LEVEL, token_count


MIN_GROUP_TOKENS = 32
MAX_GROUP_TOKENS = 1024


def build_section_ids(levels: list[int], target_level: int | None) -> list[int]:
    section_ids: list[int] = []
    sid = 0
    for index, level in enumerate(levels):
        if target_level is not None and level <= target_level and index > 0:
            sid += 1
        section_ids.append(sid)
    return section_ids


def group_record_groups(
    records: list[dict[str, object]],
    levels: list[int],
    *,
    target_level: int | None,
) -> list[list[dict[str, object]]]:
    section_ids = build_section_ids(levels, target_level)
    record_groups: list[list[dict[str, object]]] = []
    token_total = 0
    last_sid = -2

    for record, section_id in zip(records, section_ids):
        text = str(record["text"])
        level = int(record["level"])
        if not text.strip():
            continue

        token_size = token_count(text)
        should_merge = (
            record_groups
            and (
                token_total < MIN_GROUP_TOKENS
                or (token_total < MAX_GROUP_TOKENS and section_id == last_sid)
            )
        )

        if level == BODY_LEVEL and should_merge:
            record_groups[-1].append(record)
            token_total += token_size
        else:
            record_groups.append([record])
            token_total = token_size

        last_sid = section_id

    return record_groups

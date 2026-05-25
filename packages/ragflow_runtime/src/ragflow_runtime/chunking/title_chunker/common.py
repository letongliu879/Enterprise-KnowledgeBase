from __future__ import annotations

#
# Adapted from RAGFlow title_chunker/common.py under Apache 2.0.
# This local vendor keeps the grouping semantics while replacing upstream
# runtime-specific dependencies with Reality-RAG-local pure helpers.
#

from collections import Counter
import re
import sys


BODY_LEVEL = sys.maxsize - 1
DEFAULT_LEVEL_GROUPS = [
    [r"^#[^#]", r"^##[^#]", r"^###[^#]", r"^####[^#]", r"^#####[^#]", r"^######[^#]?"],
    [
        r"第[零一二三四五六七八九十百0-9]+(分?编|部分)",
        r"第[零一二三四五六七八九十百0-9]+章",
        r"第[零一二三四五六七八九十百0-9]+节",
        r"第[零一二三四五六七八九十百0-9]+条",
        r"[\(（][零一二三四五六七八九十百]+[\)）]",
    ],
    [
        r"第[0-9]+章",
        r"第[0-9]+节",
        r"[0-9]{1,2}[\. 、]",
        r"[0-9]{1,2}\.[0-9]{1,2}($|[^a-zA-Z/%~.-])",
        r"[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}",
    ],
    [
        r"第[零一二三四五六七八九十百0-9]+章",
        r"第[零一二三四五六七八九十百0-9]+节",
        r"[零一二三四五六七八九十百]+[ 、]",
        r"[\(（][零一二三四五六七八九十百]+[\)）]",
        r"[\(（][0-9]{,2}[\)）]",
    ],
    [
        r"PART (ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)",
        r"Chapter (I+V?|VI*|XI|IX|X)",
        r"Section [0-9]+",
        r"Article [0-9]+",
    ],
]


def token_count(text: str) -> int:
    terms = [term for term in re.split(r"\s+", text.strip()) if term]
    return max(len(terms), 1) if text.strip() else 0


def resolve_target_level(levels: list[int], hierarchy: int | None) -> int | None:
    title_levels = sorted({level for level in levels if 0 < level < BODY_LEVEL})
    if not title_levels:
        return None
    hierarchy_num = max(int(hierarchy or 1), 1)
    return title_levels[min(hierarchy_num, len(title_levels)) - 1]


def not_bullet(line: str) -> bool:
    patterns = [
        r"0",
        r"[0-9]+ +[0-9~个只-]",
        r"[0-9]+\.{2,}",
    ]
    return any(re.match(pattern, line) for pattern in patterns)


def not_title(text: str) -> bool:
    if re.match(r"第[零一二三四五六七八九十百0-9]+条", text):
        return False
    if len(text.split()) > 12 or (text.find(" ") < 0 and len(text) >= 32):
        return True
    return bool(re.search(r"[,;，。；！!]", text))


def match_regex_level(text: str, level_group: list[str]) -> int | None:
    stripped = text.strip()
    for level, pattern in enumerate(level_group, start=1):
        if re.match(pattern, stripped) and not not_bullet(stripped):
            return level
    return None


def select_level_group(lines: list[str], raw_levels: list[list[str]]) -> list[str]:
    if not raw_levels:
        return []

    hits = [0] * len(raw_levels)
    for index, group in enumerate(raw_levels):
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            for pattern in group:
                if re.match(pattern, stripped) and not not_bullet(stripped):
                    hits[index] += 1
                    break

    maximum = 0
    selected = -1
    for index, hit in enumerate(hits):
        if hit <= maximum:
            continue
        selected = index
        maximum = hit

    if selected < 0:
        return []
    return [pattern for pattern in raw_levels[selected] if pattern]


def match_layout_level(text: str, layout: str, fallback_level: int) -> int:
    if re.search(r"(section|title|head)", layout, re.I) and not not_title(text.split("@")[0].strip()):
        return fallback_level
    return BODY_LEVEL


def resolve_frequency_levels(
    line_records: list[dict[str, object]],
    raw_levels: list[list[str]],
) -> dict[str, object]:
    level_group = select_level_group(
        [str(record["text"]) for record in line_records],
        raw_levels,
    )
    fallback_level = len(level_group) + 1
    levels: list[int] = []
    for record in line_records:
        if str(record.get("doc_type_kwd") or "text") != "text":
            levels.append(BODY_LEVEL)
            continue
        level = match_regex_level(str(record["text"]), level_group)
        if level is not None:
            levels.append(level)
            continue
        levels.append(
            match_layout_level(
                str(record["text"]),
                str(record.get("layout") or ""),
                fallback_level,
            )
        )

    most_level = None
    for level, _ in Counter(levels).most_common():
        if level < BODY_LEVEL:
            most_level = level
            break

    return {
        "levels": levels,
        "most_level": most_level,
        "source": "frequency",
        "level_group": level_group,
    }

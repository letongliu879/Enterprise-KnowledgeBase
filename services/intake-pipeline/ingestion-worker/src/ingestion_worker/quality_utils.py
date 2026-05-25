"""Quality assessment utilities for ingestion pipeline."""

from __future__ import annotations

import re


def detect_garbled_text(text: str) -> float:
    """Proportion of words that appear garbled (>50% non-ASCII, excluding short words)."""
    if not text:
        return 0.0
    words = text.split()
    if not words:
        return 0.0
    garbled = 0
    for word in words:
        clean = word.strip(".,;:!?()[]{}\"\"'\"")
        if len(clean) > 3:
            non_ascii = sum(1 for ch in clean if ord(ch) > 127)
            if non_ascii / len(clean) > 0.5:
                garbled += 1
    return garbled / len(words)


def assess_table_quality(text: str) -> float:
    """Score table extraction: 1.0 if no tables or well-formed; 0.5 if broken tables."""
    lines = text.splitlines()
    table_lines = [l for l in lines if "|" in l]
    if not table_lines:
        return 1.0
    separator_lines = [l for l in table_lines if re.match(r"^\|?[\s\-:|]+\|?$", l.strip())]
    return 1.0 if separator_lines else 0.5


def detect_truncation(text: str, file_size: int) -> bool:
    """Heuristic: large source file with tiny output, or truncation indicators in last lines."""
    if file_size == 0:
        return False
    if file_size > 10_000 and len(text) < 100:
        return True
    last_lines = text.strip().split("\n")[-3:]
    indicators = ["...", "[truncated]", "continued", "page", "see appendix"]
    return any(ind in line.lower() for line in last_lines for ind in indicators)

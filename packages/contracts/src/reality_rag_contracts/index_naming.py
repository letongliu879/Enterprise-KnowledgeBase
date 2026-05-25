"""Shared helpers for physical backend index / collection naming."""

from __future__ import annotations

import re


_INVALID_NAME_CHARS = re.compile(r"[^a-z0-9._-]+")
_DUPLICATE_SEPARATORS = re.compile(r"[-._]{2,}")


def _sanitize_name(value: str) -> str:
    normalized = _INVALID_NAME_CHARS.sub("-", value.strip().lower())
    normalized = _DUPLICATE_SEPARATORS.sub("-", normalized).strip("-._")
    return normalized or "default"


def build_versioned_backend_name(
    *,
    prefix: str,
    collection_id: str,
    index_version: str,
) -> str:
    """Build a stable physical backend resource name for one index version.

    If `index_version` already includes the collection slug, do not repeat it.
    """

    normalized_prefix = _sanitize_name(prefix)
    normalized_collection = _sanitize_name(collection_id)
    normalized_version = _sanitize_name(index_version)

    if (
        normalized_version == normalized_collection
        or normalized_version.startswith(f"{normalized_collection}-")
    ):
        suffix = normalized_version
    else:
        suffix = f"{normalized_collection}-{normalized_version}"
    return f"{normalized_prefix}-{suffix}"


def build_opensearch_index_name(
    *,
    index_prefix: str,
    collection_id: str,
    index_version: str,
) -> str:
    return build_versioned_backend_name(
        prefix=index_prefix,
        collection_id=collection_id,
        index_version=index_version,
    )


def build_qdrant_collection_name(
    *,
    collection_prefix: str,
    collection_id: str,
    index_version: str,
) -> str:
    return build_versioned_backend_name(
        prefix=collection_prefix,
        collection_id=collection_id,
        index_version=index_version,
    )

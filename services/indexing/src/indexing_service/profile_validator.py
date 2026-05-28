"""Parser profile validation and canonicalization.

Indexing runtime is the validator/owner of parser profiles.
Admin is the control plane that creates/publishes profiles.
This module validates admin-submitted profiles and returns canonical configs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from indexing_service.parser_profiles import get_parser_profile, list_parser_profile_ids
from indexing_service.upstream_parser_config import get_parser_config


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class ParserProfileValidateResult:
    valid: bool
    canonical_config: dict[str, Any] | None
    profile_hash: str
    warnings: list[str]
    errors: list[ValidationError]
    runtime_owner: str
    validator_version: str


_SUPPORTED_PARSERS: set[str] = set(list_parser_profile_ids())


def _compute_profile_hash(parser_id: str, canonical_config: dict[str, Any]) -> str:
    """Compute a stable SHA-256 hash of the canonical config."""
    canonical_json = json.dumps(canonical_config, sort_keys=True, separators=(",", ":"))
    hash_value = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"sha256:{hash_value}"


def validate_parser_profile(
    parser_profile_id: str,
    parser_id: str,
    parser_config: dict[str, Any],
    chunk_profile_id: str | None = None,
    tenant_id: str = "",
    collection_id: str | None = None,
    version: str | int | None = None,
) -> ParserProfileValidateResult:
    """Validate a parser profile and return canonical config.

    This is a pure function: it does NOT write to admin tables,
    create ParseSnapshots, or trigger parse jobs.
    """
    warnings: list[str] = []
    errors: list[ValidationError] = []

    # Validate parser_id is supported
    if parser_id not in _SUPPORTED_PARSERS:
        errors.append(
            ValidationError(
                code="INVALID_PARSER_ID",
                message=f"Parser '{parser_id}' is not recognized by indexing runtime. "
                f"Supported parsers: {sorted(_SUPPORTED_PARSERS)}",
            )
        )
        return ParserProfileValidateResult(
            valid=False,
            canonical_config=None,
            profile_hash=_compute_profile_hash(parser_id, {}),
            warnings=warnings,
            errors=errors,
            runtime_owner="indexing",
            validator_version="indexing-v0.1.0",
        )

    # Get the parser profile template
    profile_template = get_parser_profile(parser_id)
    assert profile_template is not None

    # Build canonical config by merging defaults with provided config
    try:
        canonical_config = get_parser_config(parser_id, parser_config)
    except Exception as exc:
        errors.append(
            ValidationError(
                code="CONFIG_MERGE_ERROR",
                message=f"Failed to merge parser config: {exc}",
            )
        )
        return ParserProfileValidateResult(
            valid=False,
            canonical_config=None,
            profile_hash=_compute_profile_hash(parser_id, parser_config),
            warnings=warnings,
            errors=errors,
            runtime_owner="indexing",
            validator_version="indexing-v0.1.0",
        )

    # Validate chunk_token_num if present
    chunk_token_num = canonical_config.get("chunk_token_num")
    if chunk_token_num is not None:
        if not isinstance(chunk_token_num, int) or chunk_token_num <= 0:
            errors.append(
                ValidationError(
                    code="INVALID_CHUNK_TOKEN_NUM",
                    message=f"chunk_token_num must be a positive integer, got {chunk_token_num!r}",
                )
            )
        elif chunk_token_num < 128:
            warnings.append(
                f"chunk_token_num ({chunk_token_num}) is below recommended minimum of 128"
            )
        elif chunk_token_num > 8192:
            warnings.append(
                f"chunk_token_num ({chunk_token_num}) exceeds recommended maximum of 8192"
            )

    # Validate delimiter if present
    delimiter = canonical_config.get("delimiter")
    if delimiter is not None and not isinstance(delimiter, str):
        errors.append(
            ValidationError(
                code="INVALID_DELIMITER",
                message=f"delimiter must be a string, got {type(delimiter).__name__}",
            )
        )

    # Validate raptor config if present
    raptor = canonical_config.get("raptor")
    if isinstance(raptor, dict):
        use_raptor = raptor.get("use_raptor")
        if use_raptor is not None and not isinstance(use_raptor, bool):
            errors.append(
                ValidationError(
                    code="INVALID_RAPTOR_CONFIG",
                    message=f"raptor.use_raptor must be a boolean, got {type(use_raptor).__name__}",
                )
            )

    # Validate graphrag config if present
    graphrag = canonical_config.get("graphrag")
    if isinstance(graphrag, dict):
        use_graphrag = graphrag.get("use_graphrag")
        if use_graphrag is not None and not isinstance(use_graphrag, bool):
            errors.append(
                ValidationError(
                    code="INVALID_GRAPHRAG_CONFIG",
                    message=f"graphrag.use_graphrag must be a boolean, got {type(use_graphrag).__name__}",
                )
            )

    # Compute hash from canonical config
    profile_hash = _compute_profile_hash(parser_id, canonical_config)

    if errors:
        return ParserProfileValidateResult(
            valid=False,
            canonical_config=None,
            profile_hash=profile_hash,
            warnings=warnings,
            errors=errors,
            runtime_owner="indexing",
            validator_version="indexing-v0.1.0",
        )

    return ParserProfileValidateResult(
        valid=True,
        canonical_config=canonical_config,
        profile_hash=profile_hash,
        warnings=warnings,
        errors=errors,
        runtime_owner="indexing",
        validator_version="indexing-v0.1.0",
    )

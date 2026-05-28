"""Tests for parser profile validation and canonicalization."""

from __future__ import annotations

import pytest

from indexing_service.profile_validator import (
    ValidationError,
    validate_parser_profile,
)


class TestValidateParserProfile:
    def test_valid_naive_profile(self):
        result = validate_parser_profile(
            parser_profile_id="pp-naive-v2",
            parser_id="naive",
            parser_config={
                "chunk_token_num": 256,
                "delimiter": "\\n",
                "auto_keywords": 0,
            },
            tenant_id="tnt_default",
        )
        assert result.valid is True
        assert result.canonical_config is not None
        assert result.canonical_config["chunk_token_num"] == 256
        assert result.profile_hash.startswith("sha256:")
        assert result.runtime_owner == "indexing"
        assert result.validator_version == "indexing-v0.1.0"
        assert result.errors == []

    def test_invalid_parser_id(self):
        result = validate_parser_profile(
            parser_profile_id="pp-unknown",
            parser_id="unsupported_parser",
            parser_config={},
            tenant_id="tnt_default",
        )
        assert result.valid is False
        assert result.canonical_config is None
        assert len(result.errors) == 1
        assert result.errors[0].code == "INVALID_PARSER_ID"
        assert "unsupported_parser" in result.errors[0].message

    def test_valid_profile_with_defaults(self):
        result = validate_parser_profile(
            parser_profile_id="pp-naive-default",
            parser_id="naive",
            parser_config={},
            tenant_id="tnt_default",
        )
        assert result.valid is True
        assert result.canonical_config is not None
        # Defaults from upstream_parser_config should be merged
        assert "chunk_token_num" in result.canonical_config
        assert "raptor" in result.canonical_config

    def test_chunk_token_num_warning_low(self):
        result = validate_parser_profile(
            parser_profile_id="pp-small-chunks",
            parser_id="naive",
            parser_config={"chunk_token_num": 64},
            tenant_id="tnt_default",
        )
        assert result.valid is True
        assert any("below recommended minimum" in w for w in result.warnings)

    def test_chunk_token_num_warning_high(self):
        result = validate_parser_profile(
            parser_profile_id="pp-large-chunks",
            parser_id="naive",
            parser_config={"chunk_token_num": 10000},
            tenant_id="tnt_default",
        )
        assert result.valid is True
        assert any("exceeds recommended maximum" in w for w in result.warnings)

    def test_invalid_chunk_token_num_type(self):
        result = validate_parser_profile(
            parser_profile_id="pp-bad-chunks",
            parser_id="naive",
            parser_config={"chunk_token_num": "not_a_number"},
            tenant_id="tnt_default",
        )
        assert result.valid is False
        assert any(e.code == "INVALID_CHUNK_TOKEN_NUM" for e in result.errors)

    def test_invalid_delimiter_type(self):
        result = validate_parser_profile(
            parser_profile_id="pp-bad-delimiter",
            parser_id="naive",
            parser_config={"delimiter": 123},
            tenant_id="tnt_default",
        )
        assert result.valid is False
        assert any(e.code == "INVALID_DELIMITER" for e in result.errors)

    def test_invalid_raptor_config(self):
        result = validate_parser_profile(
            parser_profile_id="pp-bad-raptor",
            parser_id="naive",
            parser_config={"raptor": {"use_raptor": "yes"}},
            tenant_id="tnt_default",
        )
        assert result.valid is False
        assert any(e.code == "INVALID_RAPTOR_CONFIG" for e in result.errors)

    def test_invalid_graphrag_config(self):
        result = validate_parser_profile(
            parser_profile_id="pp-bad-graphrag",
            parser_id="naive",
            parser_config={"graphrag": {"use_graphrag": 1}},
            tenant_id="tnt_default",
        )
        assert result.valid is False
        assert any(e.code == "INVALID_GRAPHRAG_CONFIG" for e in result.errors)

    def test_hash_stability(self):
        result1 = validate_parser_profile(
            parser_profile_id="pp-stable",
            parser_id="naive",
            parser_config={"chunk_token_num": 512},
            tenant_id="tnt_default",
        )
        result2 = validate_parser_profile(
            parser_profile_id="pp-stable",
            parser_id="naive",
            parser_config={"chunk_token_num": 512},
            tenant_id="tnt_default",
        )
        assert result1.valid is True
        assert result2.valid is True
        assert result1.profile_hash == result2.profile_hash

    def test_hash_changes_with_config(self):
        result1 = validate_parser_profile(
            parser_profile_id="pp-stable",
            parser_id="naive",
            parser_config={"chunk_token_num": 512},
            tenant_id="tnt_default",
        )
        result2 = validate_parser_profile(
            parser_profile_id="pp-stable",
            parser_id="naive",
            parser_config={"chunk_token_num": 1024},
            tenant_id="tnt_default",
        )
        assert result1.valid is True
        assert result2.valid is True
        assert result1.profile_hash != result2.profile_hash

    def test_no_side_effects_no_db_write(self):
        result = validate_parser_profile(
            parser_profile_id="pp-no-side-effects",
            parser_id="naive",
            parser_config={},
            tenant_id="tnt_default",
        )
        assert result.valid is True
        # This is a pure function — no DB writes, no ParseSnapshot creation,
        # no parse job triggers. The test passing confirms the function signature.

    def test_all_optional_fields(self):
        result = validate_parser_profile(
            parser_profile_id="pp-full",
            parser_id="presentation",
            parser_config={"chunk_token_num": 256},
            chunk_profile_id="cp-default",
            tenant_id="tnt_default",
            collection_id="col-finance-policy",
            version=3,
        )
        assert result.valid is True
        assert result.canonical_config is not None

    def test_paper_parser_valid(self):
        result = validate_parser_profile(
            parser_profile_id="pp-paper",
            parser_id="paper",
            parser_config={},
            tenant_id="tnt_default",
        )
        assert result.valid is True
        assert result.canonical_config is not None

    def test_qa_parser_valid(self):
        result = validate_parser_profile(
            parser_profile_id="pp-qa",
            parser_id="qa",
            parser_config={},
            tenant_id="tnt_default",
        )
        assert result.valid is True
        assert result.canonical_config is not None

"""Verify PostgreSQL vs object-storage boundary in persistence schema.

These tests ensure the Batch 3.5 storage boundary definitions (B35)
are reflected in the actual SQLAlchemy ORM models.
"""

import pytest
from sqlalchemy import inspect

from reality_rag_persistence.database import create_all, override_url_for_testing
from reality_rag_persistence.models import (
    DocumentModel,
    IngestionJobModel,
)


@pytest.fixture(autouse=True)
def _setup():
    override_url_for_testing("sqlite:///:memory:")
    create_all()


def _column_names(model_class):
    inspector = inspect(model_class)
    return {c.name for c in inspector.columns}


def _column_types(model_class):
    inspector = inspect(model_class)
    return {c.name: str(c.type) for c in inspector.columns}


# ── Document table ──────────────────────────────────────────────────────────


def test_documents_has_processing_summary():
    cols = _column_names(DocumentModel)
    assert "processing_summary" in cols


def test_documents_has_asset_paths():
    cols = _column_names(DocumentModel)
    assert "asset_paths" in cols


def test_documents_quality_summary_exists():
    cols = _column_names(DocumentModel)
    assert "quality_summary" in cols


def test_documents_no_full_canonical_body_column():
    """Documents table must not store the full canonical.md body."""
    cols = _column_names(DocumentModel)
    assert "canonical_md" not in cols
    assert "canonical_body" not in cols
    assert "full_text" not in cols


# ── Ingestion Jobs table ────────────────────────────────────────────────────


def test_ingestion_jobs_has_report_asset_path():
    cols = _column_names(IngestionJobModel)
    assert "report_asset_path" in cols


def test_conversion_report_is_json():
    """conversion_report stores a transitional JSON summary only."""
    types = _column_types(IngestionJobModel)
    assert "conversion_report" in types
    assert "JSON" in types["conversion_report"].upper()


# ── Boundary: PostgreSQL stores summaries, sidecar stores full bodies ──────


def test_documents_has_governance_metadata_columns():
    """PostgreSQL stores lifecycle, state, authority — not full governance assets."""
    cols = _column_names(DocumentModel)
    for c in (
        "publish_status",
        "index_status",
        "authority_level",
        "governance_level",
        "access_policy",
        "domain_tags",
        "risk_tags",
    ):
        assert c in cols, f"governance column {c} missing"

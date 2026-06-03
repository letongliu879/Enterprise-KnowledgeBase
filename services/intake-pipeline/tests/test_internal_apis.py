"""Route-boundary tests for the compatibility intake API."""

from intake_pipeline.main import app


def _paths() -> set[str]:
    return {route.path for route in app.routes}


def test_compat_root_no_longer_owns_source_file_mutation_routes():
    paths = _paths()
    assert "/internal/source-files" not in paths
    assert "/internal/source-files/{source_file_id}/claim" not in paths
    assert "/internal/source-files/{source_file_id}/consume" not in paths
    assert "/internal/source-files/{source_file_id}/mark-cleanable" not in paths
    assert "/internal/source-files/{source_file_id}/clean" not in paths
    assert "/internal/source-files/{source_file_id}/fail" not in paths


def test_compat_root_still_exposes_legacy_document_entrypoints():
    paths = _paths()
    assert "/health" in paths
    assert "/v1/documents" in paths
    assert "/v1/documents/{source_file_id}" in paths
    assert "/v1/documents/{source_file_id}/approval-tickets" in paths
    assert "/v1/documents/{source_file_id}/approve-and-publish" in paths


def test_compat_root_still_exposes_readonly_diagnostic_views():
    paths = _paths()
    assert "/internal/source-files/{source_file_id}" in paths
    assert "/internal/intake-jobs/{intake_job_id}" in paths
    assert "/internal/published-documents/{published_document_id}" in paths

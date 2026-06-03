"""Compatibility wrappers for shared pure stage executors."""

from __future__ import annotations

from intake_runtime.stages import pure_stages as _shared
from ingestion_worker.domains.publishing_domain import persist_document_and_policy

run_conversion_stage = _shared.run_conversion_stage
run_review_stage = _shared.run_review_stage
_logical_document_id = _shared._logical_document_id


_compat_persist_document_and_policy = persist_document_and_policy


def run_publishing_stage(inp, *, document_repo=None, policy_repo=None, persist_fn=None):
    return _shared.run_publishing_stage(
        inp,
        document_repo=document_repo,
        policy_repo=policy_repo,
        persist_fn=(persist_fn or _compat_persist_document_and_policy),
    )

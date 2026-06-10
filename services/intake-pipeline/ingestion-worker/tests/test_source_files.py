"""Tests for SourceFile repository and lifecycle."""

from __future__ import annotations

import pytest

from reality_rag_contracts import SourceFileState
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.source_files import SourceFileRepository


class TestSourceFileRepository:
    def test_create_source_file(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            sf = repo.create("src-001", "col-1", "obj_sha256_abc", "sha256:abc")
            assert sf.source_file_id == "src-001"
            assert sf.collection_id == "col-1"
            assert sf.object_id == "obj_sha256_abc"
            assert sf.content_hash == "sha256:abc"
            assert sf.state == SourceFileState.READY
            assert sf.claimed_by_job_id is None
        finally:
            session.close()

    def test_claim_succeeds_when_ready(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-002", "col-1", "obj_sha256_def", "sha256:def")
            assert repo.claim("src-002", "job-1") is True
            sf = repo.get("src-002")
            assert sf.state == SourceFileState.CLAIMED
            assert sf.claimed_by_job_id == "job-1"
        finally:
            session.close()

    def test_claim_fails_when_already_claimed(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-003", "col-1", "obj_sha256_ghi", "sha256:ghi")
            assert repo.claim("src-003", "job-1") is True
            assert repo.claim("src-003", "job-2") is False
            sf = repo.get("src-003")
            assert sf.claimed_by_job_id == "job-1"
        finally:
            session.close()

    def test_mark_consumed_from_claimed(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-004", "col-1", "obj_sha256_jkl", "sha256:jkl")
            repo.claim("src-004", "job-1")
            assert repo.mark_consumed("src-004", "job-1") is True
            sf = repo.get("src-004")
            assert sf.state == SourceFileState.CONSUMED
        finally:
            session.close()

    def test_mark_consumed_fails_wrong_job(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-005", "col-1", "obj_sha256_mno", "sha256:mno")
            repo.claim("src-005", "job-1")
            assert repo.mark_consumed("src-005", "job-2") is False
        finally:
            session.close()

    def test_mark_consumed_is_idempotent_for_same_job(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-005b", "col-1", "obj_sha256_mnob", "sha256:mnob")
            repo.claim("src-005b", "job-1")
            assert repo.mark_consumed("src-005b", "job-1") is True
            assert repo.mark_consumed("src-005b", "job-1") is True
            assert repo.mark_cleanable("src-005b", "job-1") is True
            assert repo.mark_consumed("src-005b", "job-1") is True
            assert repo.mark_cleaned("src-005b") is True
            assert repo.mark_consumed("src-005b", "job-1") is True
        finally:
            session.close()

    def test_mark_cleanable_from_claimed(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-006", "col-1", "obj_sha256_pqr", "sha256:pqr")
            repo.claim("src-006", "job-1")
            assert repo.mark_cleanable("src-006", "job-1") is True
            sf = repo.get("src-006")
            assert sf.state == SourceFileState.CLEANABLE
        finally:
            session.close()

    def test_mark_cleanable_from_consumed(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-007", "col-1", "obj_sha256_stu", "sha256:stu")
            repo.claim("src-007", "job-1")
            repo.mark_consumed("src-007", "job-1")
            assert repo.mark_cleanable("src-007", "job-1") is True
            sf = repo.get("src-007")
            assert sf.state == SourceFileState.CLEANABLE
        finally:
            session.close()

    def test_release_claim(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-008", "col-1", "obj_sha256_vwx", "sha256:vwx")
            repo.claim("src-008", "job-1")
            assert repo.release_claim("src-008") is True
            sf = repo.get("src-008")
            assert sf.state == SourceFileState.READY
            assert sf.claimed_by_job_id is None
        finally:
            session.close()

    def test_find_active_by_content_hash(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-009", "col-1", "obj_sha256_yz", "sha256:yz")
            found = repo.find_active_by_content_hash("sha256:yz", "col-1")
            assert found is not None
            assert found.source_file_id == "src-009"

            # Non-matching collection
            not_found = repo.find_active_by_content_hash("sha256:yz", "col-2")
            assert not_found is None
        finally:
            session.close()

    def test_find_active_excludes_cleanable(self):
        session = get_session()
        try:
            repo = SourceFileRepository(session)
            repo.create("src-010", "col-1", "obj_sha256_123", "sha256:123")
            repo.claim("src-010", "job-1")
            repo.mark_consumed("src-010", "job-1")
            repo.mark_cleanable("src-010", "job-1")

            found = repo.find_active_by_content_hash("sha256:123", "col-1")
            assert found is None
        finally:
            session.close()

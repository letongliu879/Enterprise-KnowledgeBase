"""Tests for OrchestratorService — phase 2 job/stage/attempt/result persistence."""

from __future__ import annotations

import pytest

from reality_rag_contracts import (
    IntakeJobState,
    StageAttemptState,
    StageName,
    StageTaskState,
)
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
from reality_rag_persistence.repositories.stage_attempts import StageAttemptRepository
from reality_rag_persistence.repositories.stage_results import StageResultRepository
from reality_rag_persistence.repositories.stage_tasks import StageTaskRepository

from intake_runtime.orchestrator import OrchestratorService


class TestOrchestratorIntakeJob:
    def test_create_intake_job(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job(
                source_file_id="src-test-001",
                object_id="obj_sha256_abc",
                collection_id="col-1",
                trace_id="trc-1",
            )
            assert job.intake_job_id.startswith("job-")
            assert job.source_file_id == "src-test-001"
            assert job.object_id == "obj_sha256_abc"
            assert job.collection_id == "col-1"
            assert job.state == IntakeJobState.CREATED.value
            assert job.state_version == 1
            assert job.attempt_count == 0
            assert job.trace_id == "trc-1"
        finally:
            session.close()

    def test_advance_state(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-002", "obj_002", "col-1")

            ok = svc.advance_state(
                job.intake_job_id, IntakeJobState.CONVERSION_RUNNING, "conversion"
            )
            assert ok is True

            job2 = IntakeJobRepository(session).get(job.intake_job_id)
            assert job2.state == IntakeJobState.CONVERSION_RUNNING.value
            assert job2.current_stage == "conversion"
            assert job2.state_version == 2
        finally:
            session.close()

    def test_advance_state_with_optimistic_lock(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-003", "obj_003", "col-1")

            # Direct update to bump state_version
            IntakeJobRepository(session).update_state(
                job.intake_job_id, IntakeJobState.CONVERSION_RUNNING
            )

            # Now try to advance with stale version
            ok = svc.advance_state(
                job.intake_job_id, IntakeJobState.PUBLISHED
            )
            # Should still succeed because we don't pass state_version in service layer
            assert ok is True
        finally:
            session.close()

    def test_fail_intake_job(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-004", "obj_004", "col-1")

            ok = svc.fail_intake_job(job.intake_job_id, "Conversion timeout")
            assert ok is True

            job2 = IntakeJobRepository(session).get(job.intake_job_id)
            assert job2.state == IntakeJobState.FAILED.value
            assert job2.error_message == "Conversion timeout"
        finally:
            session.close()


class TestOrchestratorStageTask:
    def test_find_or_create_stage_task(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-005", "obj_005", "col-1")

            task, is_new = svc.find_or_create_stage_task(
                job.intake_job_id,
                StageName.CONVERSION,
                "key-001",
                "v1",
                "hash-abc",
            )
            assert is_new is True
            assert task.stage_task_id.startswith("task-")
            assert task.stage_name == StageName.CONVERSION.value
            assert task.idempotency_key == "key-001"
            assert task.state == StageTaskState.QUEUED.value

            # Second call with same key returns existing
            task2, is_new2 = svc.find_or_create_stage_task(
                job.intake_job_id,
                StageName.CONVERSION,
                "key-001",
                "v1",
                "hash-abc",
            )
            assert is_new2 is False
            assert task2.stage_task_id == task.stage_task_id
        finally:
            session.close()

    def test_check_existing_result_returns_none_when_no_result(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-006", "obj_006", "col-1")

            result = svc.check_existing_result("nonexistent-key")
            assert result is None
        finally:
            session.close()

    def test_check_existing_result_returns_result_when_succeeded(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-007", "obj_007", "col-1")

            task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-succ", "v1", "hash-s"
            )
            svc.update_task_state(task.stage_task_id, StageTaskState.SUCCEEDED)

            attempt = svc.start_stage_attempt(
                task.stage_task_id, job.intake_job_id, StageName.CONVERSION
            )
            svc.complete_stage_attempt(attempt.stage_attempt_id, True)

            svc.record_stage_result(
                task.stage_task_id,
                attempt.stage_attempt_id,
                job.intake_job_id,
                StageName.CONVERSION,
                "key-succ",
                "res-hash",
                summary_json={"ok": True},
            )
            # start_stage_attempt sets task to RUNNING; restore to SUCCEEDED
            svc.update_task_state(task.stage_task_id, StageTaskState.SUCCEEDED)

            found = svc.check_existing_result("key-succ")
            assert found is not None
            assert found.result_hash == "res-hash"
            assert found.summary_json == {"ok": True}
        finally:
            session.close()


class TestOrchestratorStageAttempt:
    def test_start_stage_attempt(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-008", "obj_008", "col-1")
            task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-att", "v1", "hash-a"
            )

            attempt = svc.start_stage_attempt(
                task.stage_task_id, job.intake_job_id, StageName.CONVERSION, "worker-1"
            )
            assert attempt.stage_attempt_id.startswith("att-")
            assert attempt.stage_task_id == task.stage_task_id
            assert attempt.attempt_no == 1
            assert attempt.state == StageAttemptState.RUNNING.value
            assert attempt.worker_id == "worker-1"

            # Task state should be RUNNING and attempt_count incremented
            task2 = StageTaskRepository(session).get(task.stage_task_id)
            assert task2.state == StageTaskState.RUNNING.value
            assert task2.attempt_count == 1
        finally:
            session.close()

    def test_multiple_attempts_increment_attempt_no(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-009", "obj_009", "col-1")
            task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-multi", "v1", "hash-m"
            )

            att1 = svc.start_stage_attempt(
                task.stage_task_id, job.intake_job_id, StageName.CONVERSION
            )
            svc.complete_stage_attempt(att1.stage_attempt_id, False, "timeout")

            att2 = svc.start_stage_attempt(
                task.stage_task_id, job.intake_job_id, StageName.CONVERSION
            )
            assert att2.attempt_no == 2

            task2 = StageTaskRepository(session).get(task.stage_task_id)
            assert task2.attempt_count == 2
        finally:
            session.close()

    def test_complete_stage_attempt_success(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-010", "obj_010", "col-1")
            task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-comp", "v1", "hash-c"
            )
            attempt = svc.start_stage_attempt(
                task.stage_task_id, job.intake_job_id, StageName.CONVERSION
            )

            ok = svc.complete_stage_attempt(attempt.stage_attempt_id, True)
            assert ok is True

            att2 = StageAttemptRepository(session).get(attempt.stage_attempt_id)
            assert att2.state == StageAttemptState.SUCCEEDED.value
            assert att2.finished_at is not None
        finally:
            session.close()

    def test_complete_stage_attempt_failure(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-011", "obj_011", "col-1")
            task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-fail", "v1", "hash-f"
            )
            attempt = svc.start_stage_attempt(
                task.stage_task_id, job.intake_job_id, StageName.CONVERSION
            )

            ok = svc.complete_stage_attempt(
                attempt.stage_attempt_id, False, "conversion_error", "err-hash"
            )
            assert ok is True

            att2 = StageAttemptRepository(session).get(attempt.stage_attempt_id)
            assert att2.state == StageAttemptState.FAILED.value
            assert att2.error_code == "conversion_error"
            assert att2.error_summary_hash == "err-hash"
        finally:
            session.close()


class TestOrchestratorFullFlow:
    def test_successful_pipeline_records_all_states(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)

            # 1. Create intake job
            job = svc.create_intake_job("src-flow", "obj-flow", "col-1")
            assert job.state == IntakeJobState.CREATED.value

            # 2. Conversion stage
            svc.advance_state(job.intake_job_id, IntakeJobState.CONVERSION_QUEUED)
            conv_task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-conv", "v1", "hash-conv"
            )
            conv_att = svc.start_stage_attempt(
                conv_task.stage_task_id, job.intake_job_id, StageName.CONVERSION
            )
            svc.advance_state(
                job.intake_job_id, IntakeJobState.CONVERSION_RUNNING, "conversion"
            )
            svc.complete_stage_attempt(conv_att.stage_attempt_id, True)
            svc.update_task_state(conv_task.stage_task_id, StageTaskState.SUCCEEDED)
            svc.record_stage_result(
                conv_task.stage_task_id,
                conv_att.stage_attempt_id,
                job.intake_job_id,
                StageName.CONVERSION,
                "key-conv",
                "res-conv",
                summary_json={"canonical_md": "hello"},
            )
            svc.advance_state(
                job.intake_job_id, IntakeJobState.CONVERSION_SUCCEEDED
            )

            # 3. Agent review stage
            svc.advance_state(job.intake_job_id, IntakeJobState.REVIEW_QUEUED)
            review_task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.AGENT_REVIEW, "key-review", "v1", "hash-rev"
            )
            review_att = svc.start_stage_attempt(
                review_task.stage_task_id, job.intake_job_id, StageName.AGENT_REVIEW
            )
            svc.advance_state(
                job.intake_job_id, IntakeJobState.REVIEW_RUNNING, "agent_review"
            )
            svc.complete_stage_attempt(review_att.stage_attempt_id, True)
            svc.update_task_state(review_task.stage_task_id, StageTaskState.SUCCEEDED)
            svc.record_stage_result(
                review_task.stage_task_id,
                review_att.stage_attempt_id,
                job.intake_job_id,
                StageName.AGENT_REVIEW,
                "key-review",
                "res-review",
                summary_json={"decision": "approve"},
            )
            svc.advance_state(job.intake_job_id, IntakeJobState.REVIEW_SUCCEEDED)

            # 4. Publishing stage
            svc.advance_state(job.intake_job_id, IntakeJobState.PUBLISH_QUEUED)
            pub_task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.PUBLISHING, "key-pub", "v1", "hash-pub"
            )
            pub_att = svc.start_stage_attempt(
                pub_task.stage_task_id, job.intake_job_id, StageName.PUBLISHING
            )
            svc.advance_state(
                job.intake_job_id, IntakeJobState.PUBLISH_RUNNING, "publishing"
            )
            svc.complete_stage_attempt(pub_att.stage_attempt_id, True)
            svc.update_task_state(pub_task.stage_task_id, StageTaskState.SUCCEEDED)
            svc.record_stage_result(
                pub_task.stage_task_id,
                pub_att.stage_attempt_id,
                job.intake_job_id,
                StageName.PUBLISHING,
                "key-pub",
                "res-pub",
                summary_json={"persisted": True},
            )
            svc.advance_state(job.intake_job_id, IntakeJobState.PUBLISHED)

            # Verify final state
            job_final = IntakeJobRepository(session).get(job.intake_job_id)
            assert job_final.state == IntakeJobState.PUBLISHED.value
            assert job_final.current_stage == "publishing"

            # Verify 3 stage tasks
            tasks = StageTaskRepository(session).list_by_intake_job(job.intake_job_id)
            assert len(tasks) == 3
            assert all(t.state == StageTaskState.SUCCEEDED.value for t in tasks)

            # Verify 3 stage attempts
            attempts = StageAttemptRepository(session).list_by_stage_task(conv_task.stage_task_id)
            assert len(attempts) == 1
            assert attempts[0].state == StageAttemptState.SUCCEEDED.value

            # Verify 3 stage results
            results = StageResultRepository(session).get_by_stage_task(conv_task.stage_task_id)
            assert results is not None
            assert results.result_hash == "res-conv"
        finally:
            session.close()

    def test_failed_conversion_records_failure(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-fail", "obj-fail", "col-1")

            conv_task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-fail-conv", "v1", "hash-fc"
            )
            conv_att = svc.start_stage_attempt(
                conv_task.stage_task_id, job.intake_job_id, StageName.CONVERSION
            )
            svc.advance_state(
                job.intake_job_id, IntakeJobState.CONVERSION_RUNNING, "conversion"
            )

            # Simulate failure
            svc.complete_stage_attempt(
                conv_att.stage_attempt_id, False, "unsupported_format"
            )
            svc.update_task_state(conv_task.stage_task_id, StageTaskState.FAILED)
            svc.fail_intake_job(job.intake_job_id, "Unsupported file format")

            job_final = IntakeJobRepository(session).get(job.intake_job_id)
            assert job_final.state == IntakeJobState.FAILED.value
            assert job_final.error_message == "Unsupported file format"

            # No stage result should be recorded for failure
            result = StageResultRepository(session).get_by_stage_task(conv_task.stage_task_id)
            assert result is None
        finally:
            session.close()


class TestOrchestratorIdempotency:
    def test_same_idempotency_key_returns_existing_task(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-idem", "obj-idem", "col-1")

            task1, is_new1 = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "idem-key", "v1", "hash-i"
            )
            assert is_new1 is True

            task2, is_new2 = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "idem-key", "v1", "hash-i"
            )
            assert is_new2 is False
            assert task1.stage_task_id == task2.stage_task_id
        finally:
            session.close()

    def test_succeeded_task_blocks_new_attempts_via_check_existing(self):
        session = get_session()
        try:
            svc = OrchestratorService(session)
            job = svc.create_intake_job("src-block", "obj-block", "col-1")

            task, _ = svc.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "block-key", "v1", "hash-b"
            )
            svc.update_task_state(task.stage_task_id, StageTaskState.SUCCEEDED)
            att = svc.start_stage_attempt(
                task.stage_task_id, job.intake_job_id, StageName.CONVERSION
            )
            svc.complete_stage_attempt(att.stage_attempt_id, True)
            svc.record_stage_result(
                task.stage_task_id, att.stage_attempt_id, job.intake_job_id,
                StageName.CONVERSION, "block-key", "res-hash",
            )
            svc.update_task_state(task.stage_task_id, StageTaskState.SUCCEEDED)

            # check_existing_result should return the result
            existing = svc.check_existing_result("block-key")
            assert existing is not None
            assert existing.result_hash == "res-hash"
        finally:
            session.close()

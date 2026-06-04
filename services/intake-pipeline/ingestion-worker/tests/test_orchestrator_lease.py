"""Tests for Phase 2 DB lease on orchestrator stage tasks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from reality_rag_contracts import StageName, StageTaskState
from reality_rag_persistence.database import get_session

from intake_runtime.orchestrator import OrchestratorService


class TestOrchestratorLease:
    def test_acquire_lease_sets_locked_by_and_expires(self):
        session = get_session()
        try:
            orch = OrchestratorService(session)
            job = orch.create_intake_job("src-001", "obj-001", "col-1")
            task, _ = orch.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-001", "v1", "hash-001"
            )

            ok = orch.acquire_lease(task.stage_task_id, "worker-1", lease_seconds=60)
            assert ok is True

            updated = orch._task_repo.get(task.stage_task_id)
            assert updated.locked_by == "worker-1"
            assert updated.lock_expires_at is not None
            expires = updated.lock_expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            assert expires > datetime.now(timezone.utc)
        finally:
            session.close()

    def test_acquire_lease_fails_when_another_worker_holds_active_lease(self):
        session = get_session()
        try:
            orch = OrchestratorService(session)
            job = orch.create_intake_job("src-002", "obj-002", "col-1")
            task, _ = orch.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-002", "v1", "hash-002"
            )

            # Worker-1 acquires lease
            orch.acquire_lease(task.stage_task_id, "worker-1", lease_seconds=300)

            # Worker-2 cannot acquire
            ok = orch.acquire_lease(task.stage_task_id, "worker-2", lease_seconds=60)
            assert ok is False
        finally:
            session.close()

    def test_acquire_lease_succeeds_when_previous_lease_expired(self):
        session = get_session()
        try:
            orch = OrchestratorService(session)
            job = orch.create_intake_job("src-003", "obj-003", "col-1")
            task, _ = orch.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-003", "v1", "hash-003"
            )

            # Acquire with expired lock
            past = datetime.now(timezone.utc) - timedelta(seconds=1)
            orch._task_repo.set_lock(task.stage_task_id, "worker-old", past)

            ok = orch.acquire_lease(task.stage_task_id, "worker-new", lease_seconds=60)
            assert ok is True

            updated = orch._task_repo.get(task.stage_task_id)
            assert updated.locked_by == "worker-new"
        finally:
            session.close()

    def test_release_lease_clears_lock(self):
        session = get_session()
        try:
            orch = OrchestratorService(session)
            job = orch.create_intake_job("src-004", "obj-004", "col-1")
            task, _ = orch.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-004", "v1", "hash-004"
            )

            orch.acquire_lease(task.stage_task_id, "worker-1", lease_seconds=60)
            ok = orch.release_lease(task.stage_task_id)
            assert ok is True

            updated = orch._task_repo.get(task.stage_task_id)
            assert updated.locked_by is None
            assert updated.lock_expires_at is None
        finally:
            session.close()

    def test_same_worker_can_reacquire_own_lease(self):
        session = get_session()
        try:
            orch = OrchestratorService(session)
            job = orch.create_intake_job("src-005", "obj-005", "col-1")
            task, _ = orch.find_or_create_stage_task(
                job.intake_job_id, StageName.CONVERSION, "key-005", "v1", "hash-005"
            )

            orch.acquire_lease(task.stage_task_id, "worker-1", lease_seconds=300)
            ok = orch.acquire_lease(task.stage_task_id, "worker-1", lease_seconds=60)
            assert ok is True
        finally:
            session.close()

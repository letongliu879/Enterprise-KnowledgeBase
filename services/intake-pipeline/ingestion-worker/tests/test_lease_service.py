"""Tests for StageTaskLeaseService — DB lease acquire, heartbeat, release, crash recovery."""

from datetime import datetime, timezone, timedelta

from reality_rag_contracts import StageTaskState, StageName
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.stage_tasks import StageTaskRepository

from ingestion_worker.domains.lease_service import StageTaskLeaseService


class TestStageTaskLeaseAcquire:
    def _create_task(self, session):
        svc = StageTaskLeaseService(session)
        repo = StageTaskRepository(session)
        task = repo.create(
            stage_task_id="task-lease-1",
            intake_job_id="job-1",
            stage_name=StageName.CONVERSION.value,
            idempotency_key="key-1",
            schema_version="v1",
            input_hash="hash-1",
        )
        return task, svc, repo

    def test_acquire_lease_success(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            ok = lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=60)
            assert ok is True

            task2 = repo.get(task.stage_task_id)
            assert task2.locked_by == "worker-1"
            assert task2.lock_expires_at is not None
            assert task2.state == StageTaskState.RUNNING.value
        finally:
            session.close()

    def test_acquire_lease_fails_when_already_locked(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            ok1 = lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=60)
            assert ok1 is True

            # Another worker cannot acquire
            ok2 = lease_svc.acquire_lease(task.stage_task_id, "worker-2", ttl_seconds=60)
            assert ok2 is False

            task2 = repo.get(task.stage_task_id)
            assert task2.locked_by == "worker-1"
        finally:
            session.close()

    def test_acquire_lease_succeeds_after_expiry(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            # Acquire with short TTL
            ok1 = lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=1)
            assert ok1 is True

            # Manually set lock_expires_at to the past and state back to queued
            from datetime import datetime, timezone, timedelta
            from reality_rag_persistence.models import StageTaskModel
            from sqlalchemy import update
            from reality_rag_contracts import StageTaskState

            past = datetime.now(timezone.utc) - timedelta(seconds=5)
            session.execute(
                update(StageTaskModel)
                .where(StageTaskModel.stage_task_id == task.stage_task_id)
                .values(
                    lock_expires_at=past,
                    state=StageTaskState.QUEUED.value,
                )
            )
            session.flush()

            # Another worker can now acquire
            ok2 = lease_svc.acquire_lease(task.stage_task_id, "worker-2", ttl_seconds=60)
            assert ok2 is True

            task2 = repo.get(task.stage_task_id)
            assert task2.locked_by == "worker-2"
        finally:
            session.close()

    def test_acquire_lease_fails_for_succeeded_task(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            repo.update_state(task.stage_task_id, StageTaskState.SUCCEEDED)

            ok = lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=60)
            assert ok is False
        finally:
            session.close()


class TestStageTaskLeaseHeartbeat:
    def _create_task(self, session):
        svc = StageTaskLeaseService(session)
        repo = StageTaskRepository(session)
        task = repo.create(
            stage_task_id="task-hb-1",
            intake_job_id="job-1",
            stage_name=StageName.CONVERSION.value,
            idempotency_key="key-hb",
            schema_version="v1",
            input_hash="hash-hb",
        )
        return task, svc, repo

    def test_heartbeat_extends_lease(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=2)
            old_expires = repo.get(task.stage_task_id).lock_expires_at

            import time
            time.sleep(0.5)

            ok = lease_svc.heartbeat(task.stage_task_id, "worker-1", ttl_seconds=60)
            assert ok is True

            new_expires = repo.get(task.stage_task_id).lock_expires_at
            assert new_expires > old_expires
        finally:
            session.close()

    def test_heartbeat_fails_for_wrong_worker(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=60)

            ok = lease_svc.heartbeat(task.stage_task_id, "worker-2", ttl_seconds=60)
            assert ok is False
        finally:
            session.close()


class TestStageTaskLeaseRelease:
    def _create_task(self, session):
        svc = StageTaskLeaseService(session)
        repo = StageTaskRepository(session)
        task = repo.create(
            stage_task_id="task-rel-1",
            intake_job_id="job-1",
            stage_name=StageName.CONVERSION.value,
            idempotency_key="key-rel",
            schema_version="v1",
            input_hash="hash-rel",
        )
        return task, svc, repo

    def test_release_lease_clears_lock(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=60)

            ok = lease_svc.release_lease(task.stage_task_id, "worker-1")
            assert ok is True

            task2 = repo.get(task.stage_task_id)
            assert task2.locked_by is None
            assert task2.lock_expires_at is None
        finally:
            session.close()

    def test_release_lease_with_new_state(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=60)

            ok = lease_svc.release_lease(
                task.stage_task_id, "worker-1", new_state=StageTaskState.FAILED
            )
            assert ok is True

            task2 = repo.get(task.stage_task_id)
            assert task2.state == StageTaskState.FAILED.value
            assert task2.locked_by is None
        finally:
            session.close()

    def test_release_lease_fails_for_wrong_worker(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=60)

            ok = lease_svc.release_lease(task.stage_task_id, "worker-2")
            assert ok is False
        finally:
            session.close()


class TestStageTaskLeaseVerify:
    def _create_task(self, session):
        svc = StageTaskLeaseService(session)
        repo = StageTaskRepository(session)
        task = repo.create(
            stage_task_id="task-ver-1",
            intake_job_id="job-1",
            stage_name=StageName.CONVERSION.value,
            idempotency_key="key-ver",
            schema_version="v1",
            input_hash="hash-ver",
        )
        return task, svc, repo

    def test_verify_lease_true_when_held(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=60)

            assert lease_svc.verify_lease(task.stage_task_id, "worker-1") is True
        finally:
            session.close()

    def test_verify_lease_false_when_expired(self):
        session = get_session()
        try:
            task, lease_svc, repo = self._create_task(session)
            lease_svc.acquire_lease(task.stage_task_id, "worker-1", ttl_seconds=60)

            # Manually set lock_expires_at to the past
            from datetime import datetime, timezone, timedelta
            from reality_rag_persistence.models import StageTaskModel
            from sqlalchemy import update

            past = datetime.now(timezone.utc) - timedelta(seconds=5)
            session.execute(
                update(StageTaskModel)
                .where(StageTaskModel.stage_task_id == task.stage_task_id)
                .values(lock_expires_at=past)
            )
            session.flush()

            assert lease_svc.verify_lease(task.stage_task_id, "worker-1") is False
        finally:
            session.close()

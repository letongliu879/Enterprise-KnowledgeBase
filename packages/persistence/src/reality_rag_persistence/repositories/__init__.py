"""Repository layer — each module exposes a class that wraps SQLAlchemy Session."""

from .application_profiles import ApplicationProfileRepository
from .approval_audit_log import ApprovalAuditLogRepository
from .approval_tickets import ApprovalTicketRepository
from .consumer_idempotency import ConsumerIdempotencyRepository
from .outbox_events import OutboxEventRepository
from .published_document_lifecycle_audit import PublishedDocumentLifecycleAuditRepository
from .publish_jobs import PublishJobRepository
from .reindex_jobs import ReindexJobRepository
from .published_documents import PublishedDocumentRepository
from .collections import CollectionRepository
from .chunk_registry import ChunkRegistryRepository
from .run_audit import (
    RunStepEntry,
    RunStepRepository,
    RunTraceEntry,
    RunTraceRepository,
    TraceArtifactEntry,
    TraceArtifactRepository,
)
from .document_policies import DocumentPolicyRepository
from .documents import DocumentRepository
from .index_registry import IndexRegistryRepository, IndexVersionEntry
from .index_versions import IndexVersionRepository
from .indexed_documents import IndexedDocumentRepository
from .index_build_jobs import IndexBuildJobRepository
from .ingestion import IngestionRepository
from .intake_jobs import IntakeJobRepository
from .jobs import JobRepository
from .malware_scan_results import MalwareScanResultRepository
from .object_blobs import ObjectBlobRepository
from .principal_profiles import PrincipalProfileRepository
from .parse_snapshots import ParseSnapshotRepository
from .source_files import SourceFileRepository
from .stage_attempts import StageAttemptRepository
from .stage_results import StageResultRepository
from .stage_tasks import StageTaskRepository
from .tenants import TenantRepository
from .upload_sessions import UploadSessionRepository

__all__ = [
    "ApplicationProfileRepository",
    "ApprovalAuditLogRepository",
    "ApprovalTicketRepository",
    "ConsumerIdempotencyRepository",
    "OutboxEventRepository",
    "PublishedDocumentRepository",
    "PublishedDocumentLifecycleAuditRepository",
    "PublishJobRepository",
    "ReindexJobRepository",
    "CollectionRepository",
    "ChunkRegistryRepository",
    "RunTraceRepository",
    "RunTraceEntry",
    "RunStepRepository",
    "RunStepEntry",
    "TraceArtifactRepository",
    "TraceArtifactEntry",
    "DocumentPolicyRepository",
    "DocumentRepository",
    "IndexBuildJobRepository",
    "IndexedDocumentRepository",
    "IndexRegistryRepository",
    "IndexVersionEntry",
    "IndexVersionRepository",
    "IngestionRepository",
    "IntakeJobRepository",
    "JobRepository",
    "MalwareScanResultRepository",
    "ObjectBlobRepository",
    "PrincipalProfileRepository",
    "ParseSnapshotRepository",
    "SourceFileRepository",
    "StageAttemptRepository",
    "StageResultRepository",
    "StageTaskRepository",
    "TenantRepository",
    "UploadSessionRepository",
]

"""FastAPI application for the Document Service.

This service owns:
  - Upload session lifecycle
  - Object blob management (content-hash dedup, ref counting)
  - Source file lifecycle (state machine)
  - Malware scan lifecycle
  - FileReady outbox events
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from reality_rag_contracts import HealthResponse, SourceFileState, UploadSessionStatus
from reality_rag_documents import DocumentService
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository

app = FastAPI(
    title="Document Service",
    description="Source file lifecycle and object storage for Reality-RAG",
    version="0.1.0",
)

_UPLOAD_CHUNK_SIZE = 1024 * 1024
_VALID_VISIBILITIES = {"INTERNAL", "EXTERNAL"}


def _serialize_state(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _staging_root() -> Path:
    configured = os.environ.get("DOCUMENT_STAGING_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "reality-rag-document-service"


def _sanitize_filename(name: str) -> str:
    candidate = Path(name or "").name.strip()
    if not candidate:
        return "upload.bin"
    sanitized = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in candidate)
    return sanitized.strip("._") or "upload.bin"


def _upload_temp_path(upload_id: str, sanitized_name: str) -> Path:
    return _staging_root() / "_tmp" / upload_id / sanitized_name


def _cleanup_temp_path(path: Path | None) -> None:
    if path is None:
        return
    try:
        if path.exists():
            path.unlink()
    except OSError:
        return
    current = path.parent
    root = _staging_root()
    while current != root and root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


async def _write_upload_and_hash(upload: UploadFile, destination: Path) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = await upload.read(_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                size_bytes += len(chunk)
    finally:
        await upload.close()
    return f"sha256:{digest.hexdigest()}", size_bytes


def _build_duplicate_response(
    *,
    reason: str,
    upload_id: str,
    content_hash: str,
    source_file=None,
    intake_job=None,
    existing_doc_id: str | None = None,
) -> dict:
    payload = {
        "duplicate": True,
        "reason": reason,
        "upload_id": upload_id,
        "content_hash": content_hash,
        "source_file_id": None,
        "intake_job_id": None,
        "object_id": None,
        "status": "duplicate",
        "existing_doc_id": existing_doc_id,
    }
    if source_file is not None:
        payload["source_file_id"] = source_file.source_file_id
        payload["object_id"] = source_file.object_id
        payload["status"] = _serialize_state(source_file.state)
    if intake_job is not None:
        payload["intake_job_id"] = intake_job.intake_job_id
    return payload


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="document-service",
        version="0.1.0",
    )


@app.post("/upload")
async def upload_file(
    collection_id: str = Form(...),
    visibility: str = Form("INTERNAL"),
    upload_id: str | None = Form(None),
    file: UploadFile = File(...),
) -> dict:
    session = get_session()
    temp_path: Path | None = None
    try:
        if CollectionRepository(session).get(collection_id) is None:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found")

        normalized_visibility = visibility.upper()
        if normalized_visibility not in _VALID_VISIBILITIES:
            raise HTTPException(status_code=400, detail="visibility invalid")

        svc = DocumentService(session)
        if upload_id:
            upload_session = svc.create_upload_session(source="web", upload_id=upload_id)
        else:
            upload_session = svc.create_upload_session(source="web")
        upload_id = upload_session.upload_id

        sanitized_name = _sanitize_filename(file.filename or "")
        original_name = file.filename or sanitized_name
        temp_path = _upload_temp_path(upload_id, sanitized_name)
        content_hash, size_bytes = await _write_upload_and_hash(file, temp_path)

        doc_repo = DocumentRepository(session)
        is_duplicate, existing_doc_id = svc.dedup_check(content_hash, collection_id, doc_repo)
        if is_duplicate:
            source_file = None
            intake_job = None
            reason = "duplicate_published_document"
            if existing_doc_id is None:
                reason = "duplicate_active_source_file"
                source_file = SourceFileRepository(session).find_active_by_content_hash(
                    content_hash, collection_id
                )
                if source_file is not None:
                    intake_job = IntakeJobRepository(session).get_by_source_file_id(
                        source_file.source_file_id
                    )

            svc.complete_upload_session(upload_id, received_size=size_bytes)
            session.commit()
            _cleanup_temp_path(temp_path)
            return _build_duplicate_response(
                reason=reason,
                upload_id=upload_id,
                content_hash=content_hash,
                source_file=source_file,
                intake_job=intake_job,
                existing_doc_id=existing_doc_id,
            )

        obj = svc.get_or_create_object_blob(
            content_hash=content_hash,
            storage_key=str(temp_path),
            size_bytes=size_bytes,
        )
        source_file = svc.create_source_file(
            collection_id=collection_id,
            object_id=obj.object_id,
            content_hash=content_hash,
            upload_id=upload_id,
            visibility=normalized_visibility,
            original_name=original_name,
            sanitized_name=sanitized_name,
            size_bytes=size_bytes,
            state=SourceFileState.UPLOADED,
        )
        svc.complete_upload_session(upload_id, received_size=size_bytes)
        started = svc.start_scan(source_file.source_file_id)
        if started is None:
            raise RuntimeError(f"failed to start scan for source file {source_file.source_file_id}")
        completed = svc.complete_scan(source_file.source_file_id)
        if completed is None:
            raise RuntimeError(
                f"failed to complete scan for source file {source_file.source_file_id}"
            )
        session.commit()
        return {
            "duplicate": False,
            "upload_id": upload_id,
            "source_file_id": completed.source_file_id,
            "intake_job_id": None,
            "object_id": completed.object_id,
            "collection_id": completed.collection_id,
            "content_hash": completed.content_hash,
            "visibility": completed.visibility,
            "status": _serialize_state(completed.state),
            "size_bytes": completed.size_bytes,
        }
    except HTTPException:
        session.rollback()
        _cleanup_temp_path(temp_path)
        raise
    except Exception as exc:
        session.rollback()
        _cleanup_temp_path(temp_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class CreateUploadSessionRequest(BaseModel):
    source: str = "web"
    user_id: str | None = None
    trace_id: str = ""
    expected_size: int | None = None
    expected_sha256: str | None = None


@app.post("/internal/upload-sessions")
async def create_upload_session(request: CreateUploadSessionRequest) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        upl = svc.create_upload_session(
            source=request.source,
            user_id=request.user_id,
            trace_id=request.trace_id,
            expected_size=request.expected_size,
            expected_sha256=request.expected_sha256,
        )
        session.commit()
        return {
            "upload_id": upl.upload_id,
            "status": upl.status,
            "source": upl.source,
        }
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class CompleteUploadRequest(BaseModel):
    received_size: int


@app.post("/internal/upload-sessions/{upload_id}/complete")
async def complete_upload_session(upload_id: str, request: CompleteUploadRequest) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        upl = svc.complete_upload_session(upload_id, request.received_size)
        if upl is None:
            raise HTTPException(status_code=404, detail="Upload session not found")
        session.commit()
        return {
            "upload_id": upl.upload_id,
            "status": upl.status,
            "received_size": upl.received_size,
        }
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class GetOrCreateObjectRequest(BaseModel):
    content_hash: str
    storage_key: str
    size_bytes: int = 0


@app.post("/internal/object-blobs/get-or-create")
async def get_or_create_object_blob(request: GetOrCreateObjectRequest) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        obj = svc.get_or_create_object_blob(
            content_hash=request.content_hash,
            storage_key=request.storage_key,
            size_bytes=request.size_bytes,
        )
        session.commit()
        return {
            "object_id": obj.object_id,
            "content_hash": obj.content_hash,
            "storage_key": obj.storage_key,
            "ref_count": obj.ref_count,
            "status": obj.status,
        }
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


@app.post("/internal/object-blobs/{object_id}/gc")
async def gc_object_blob(object_id: str) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        deleted = svc.gc_object_blob(object_id)
        session.commit()
        return {"deleted": deleted}
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class CreateSourceFileRequest(BaseModel):
    collection_id: str
    object_id: str
    content_hash: str
    upload_id: str | None = None
    visibility: str = "INTERNAL"
    original_name: str = ""
    sanitized_name: str = ""
    size_bytes: int = 0
    state: str = "READY"


@app.post("/internal/source-files")
async def create_source_file(request: CreateSourceFileRequest) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        state_enum = SourceFileState(request.state)
        sf = svc.create_source_file(
            collection_id=request.collection_id,
            object_id=request.object_id,
            content_hash=request.content_hash,
            upload_id=request.upload_id,
            visibility=request.visibility,
            original_name=request.original_name,
            sanitized_name=request.sanitized_name,
            size_bytes=request.size_bytes,
            state=state_enum,
        )
        session.commit()
        return {
            "source_file_id": sf.source_file_id,
            "collection_id": sf.collection_id,
            "object_id": sf.object_id,
            "content_hash": sf.content_hash,
            "state": _serialize_state(sf.state),
        }
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class ClaimRequest(BaseModel):
    job_id: str


@app.get("/internal/source-files/{source_file_id}")
async def get_source_file(source_file_id: str) -> dict:
    session = get_session()
    try:
        repo = SourceFileRepository(session)
        sf = repo.get(source_file_id)
        if sf is None:
            raise HTTPException(status_code=404, detail=f"Source file {source_file_id} not found")
        return {
            "source_file_id": sf.source_file_id,
            "collection_id": sf.collection_id,
            "object_id": sf.object_id,
            "content_hash": sf.content_hash,
            "state": _serialize_state(sf.state),
            "upload_id": sf.upload_id,
            "claimed_by": sf.claimed_by,
            "claimed_at": sf.claimed_at.isoformat() if sf.claimed_at else None,
            "consumed_by": sf.consumed_by,
            "consumed_at": sf.consumed_at.isoformat() if sf.consumed_at else None,
            "created_at": sf.created_at.isoformat() if sf.created_at else None,
            "updated_at": sf.updated_at.isoformat() if sf.updated_at else None,
        }
    finally:
        session.close()


@app.post("/internal/source-files/{source_file_id}/claim")
async def claim_source_file(source_file_id: str, request: ClaimRequest) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        ok = svc.claim_source_file(source_file_id, request.job_id)
        if not ok:
            raise HTTPException(status_code=409, detail="Claim failed")
        session.commit()
        return {"claimed": True}
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class MarkConsumedRequest(BaseModel):
    job_id: str


@app.post("/internal/source-files/{source_file_id}/mark-consumed")
async def mark_consumed(source_file_id: str, request: MarkConsumedRequest) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        ok = svc.mark_consumed(source_file_id, request.job_id)
        if not ok:
            raise HTTPException(status_code=409, detail="Mark consumed failed")
        session.commit()
        return {"consumed": True}
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class MarkCleanableRequest(BaseModel):
    job_id: str


@app.post("/internal/source-files/{source_file_id}/mark-cleanable")
async def mark_cleanable(source_file_id: str, request: MarkCleanableRequest) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        ok = svc.mark_cleanable(source_file_id, request.job_id)
        if not ok:
            raise HTTPException(status_code=409, detail="Mark cleanable failed")
        session.commit()
        return {"cleanable": True}
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


@app.post("/internal/source-files/{source_file_id}/gc")
async def gc_source_file(source_file_id: str) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        ok = svc.gc_source_file(source_file_id)
        session.commit()
        return {"cleaned": ok}
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


@app.post("/internal/source-files/{source_file_id}/release-claim")
async def release_claim(source_file_id: str) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        ok = svc.release_claim(source_file_id)
        session.commit()
        return {"released": ok}
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


@app.post("/internal/source-files/{source_file_id}/start-scan")
async def start_scan(source_file_id: str) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        sf = svc.start_scan(source_file_id)
        if sf is None:
            raise HTTPException(status_code=404, detail="Source file not found")
        session.commit()
        return {"source_file_id": sf.source_file_id, "state": _serialize_state(sf.state)}
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


@app.post("/internal/source-files/{source_file_id}/complete-scan")
async def complete_scan(source_file_id: str) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        sf = svc.complete_scan(source_file_id)
        if sf is None:
            raise HTTPException(
                status_code=404,
                detail="Source file not found or not in SCANNING state",
            )
        session.commit()
        return {"source_file_id": sf.source_file_id, "state": _serialize_state(sf.state)}
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class DedupCheckRequest(BaseModel):
    content_hash: str
    collection_id: str


@app.post("/internal/dedup-check")
async def dedup_check(request: DedupCheckRequest) -> dict:
    session = get_session()
    try:
        svc = DocumentService(session)
        doc_repo = DocumentRepository(session)
        is_dup, existing_doc_id = svc.dedup_check(
            request.content_hash,
            request.collection_id,
            doc_repo,
        )
        return {
            "is_duplicate": is_dup,
            "existing_doc_id": existing_doc_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()

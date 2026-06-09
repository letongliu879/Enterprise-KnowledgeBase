"""FastAPI application for Reality-RAG Workbench API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth.routes import router as auth_router
from .upload_sessions.routes import router as upload_router
from .parser_selection.routes import router as parser_router
from .parse_preview.routes import router as preview_router
from .parse_snapshot.routes import router as snapshot_router
from .chunks.routes import router as chunk_router
from .tickets.routes import router as ticket_router
from .chunk_edits.routes import router as chunk_edit_router
from .task_projection.routes import router as task_router
from .workspace.routes import router as workspace_router
from .source_files.routes import router as source_file_router
from .commands.retrieval import router as retrieval_router
from .events import router as event_router
from .projections.routes import router as projection_router
from .documents.routes import router as document_router
from .collections.routes import router as collections_router
from .retrieval_profiles.routes import router as retrieval_profiles_router
from .health.routes import router as health_router


@asynccontextmanager
async def _build_lifespan():
    """Application lifespan manager.

    Projection is the sole read model; no background reconciler needed.
    """
    yield


def create_app() -> FastAPI:
    """Workbench API factory."""
    application = FastAPI(
        title="Reality-RAG Workbench",
        version="0.1.0",
        lifespan=lambda app: _build_lifespan(),
    )

    application.include_router(auth_router)
    application.include_router(upload_router)
    application.include_router(parser_router)
    application.include_router(preview_router)
    application.include_router(snapshot_router)
    application.include_router(chunk_router)
    application.include_router(ticket_router)
    application.include_router(chunk_edit_router)
    application.include_router(task_router)
    application.include_router(workspace_router)
    application.include_router(source_file_router)
    application.include_router(retrieval_router)
    application.include_router(event_router)
    application.include_router(document_router)
    application.include_router(projection_router)
    application.include_router(collections_router)
    application.include_router(retrieval_profiles_router)
    application.include_router(health_router)

    @application.get("/workbench/health")
    def health() -> dict[str, str]:
        return {"service": "workbench", "status": "ok"}

    return application


app = create_app()

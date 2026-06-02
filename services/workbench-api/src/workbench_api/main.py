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
from .events.routes import router as event_router
from .projections.routes import router as projection_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Starts background reconciliation loop on startup.
    Gracefully cancels on shutdown.
    """
    import asyncio
    from .projections.reconciler import reconciliation_loop

    reconcile_task = asyncio.create_task(reconciliation_loop())
    yield
    reconcile_task.cancel()
    try:
        await reconcile_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Reality-RAG Workbench",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(parser_router)
app.include_router(preview_router)
app.include_router(snapshot_router)
app.include_router(chunk_router)
app.include_router(ticket_router)
app.include_router(chunk_edit_router)
app.include_router(task_router)
app.include_router(workspace_router)
app.include_router(source_file_router)
app.include_router(retrieval_router)
app.include_router(event_router)
app.include_router(projection_router)


@app.get("/workbench/health")
def health() -> dict[str, str]:
    return {"service": "workbench", "status": "ok"}

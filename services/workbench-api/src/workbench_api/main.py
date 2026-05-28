"""FastAPI application for Reality-RAG Workbench API."""

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

app = FastAPI(title="Reality-RAG Workbench", version="0.1.0")

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(parser_router)
app.include_router(preview_router)
app.include_router(snapshot_router)
app.include_router(chunk_router)
app.include_router(ticket_router)
app.include_router(chunk_edit_router)
app.include_router(task_router)


@app.get("/workbench/health")
def health() -> dict[str, str]:
    return {"service": "workbench", "status": "ok"}

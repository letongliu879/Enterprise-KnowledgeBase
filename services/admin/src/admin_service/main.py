"""FastAPI app for Reality-RAG Admin Service."""

from fastapi import FastAPI

from .database import init_database
from .identity.routes import router as identity_router
from .collection_catalog.routes import router as collection_router
from .profile_registry.routes import router as profile_router
from .api_key_registry.routes import router as api_key_router
from .ops_audit.routes import router as ops_router
from .document_ops.routes import router as document_ops_router

app = FastAPI(
    title="Reality-RAG Admin Service",
    version="0.1.0",
    description="Admin control panel for Enterprise KnowledgeBase",
)

app.include_router(identity_router)
app.include_router(collection_router)
app.include_router(profile_router)
app.include_router(api_key_router)
app.include_router(ops_router)
app.include_router(document_ops_router)


@app.on_event("startup")
def _startup() -> None:
    init_database()


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "admin", "version": "0.1.0"}

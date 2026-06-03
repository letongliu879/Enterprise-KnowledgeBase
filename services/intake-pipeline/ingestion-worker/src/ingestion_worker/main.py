"""Runtime entrypoint for the ingestion worker FastAPI app."""

from __future__ import annotations

from .app_factory import bind_default_runtime_app, create_app

app = create_app()
get_pipeline, get_monitored_ingestion_service, get_indexing_service = bind_default_runtime_app(app)

"""Aggregated health check — single endpoint for frontend status bar."""

import asyncio

from fastapi import APIRouter
import httpx

from ..config import config

router = APIRouter(prefix="/workbench/health")


async def _check_service(name: str, url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return {"status": data.get("status", "ok"), "service": name}
    except Exception:
        pass
    return {"status": "down", "service": name}


@router.get("/all")
async def health_all() -> dict:
    results = await asyncio.gather(
        _check_service("admin", f"{config.admin_base_url}/health"),
        _check_service("access", f"{config.access_base_url}/health"),
        _check_service("retrieval", f"{config.retrieval_base_url}/health"),
        _check_service("indexing", f"{config.indexing_base_url}/health"),
        _check_service("ingestion", f"{config.ingestion_worker_url}/health"),
    )
    all_healthy = all(r["status"] in ("ok", "healthy", "UP") for r in results)
    return {
        "workbench": {"status": "ok", "service": "workbench"},
        "services": {r["service"]: r for r in results},
        "all_healthy": all_healthy,
    }

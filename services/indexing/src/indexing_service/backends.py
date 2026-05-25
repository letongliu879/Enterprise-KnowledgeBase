from __future__ import annotations

import os
import uuid
from itertools import zip_longest

import httpx
from indexing_service.config import load_indexing_config, normalize_embedding_model


async def embed_texts(texts: list[str], *, config: dict[str, object] | None = None) -> list[list[float]]:
    indexing_config = load_indexing_config()
    cfg = config or {}
    base_url = str(
        cfg.get("base_url")
        or indexing_config.models.embedding_base_url
        or ""
    ).rstrip("/")
    api_key = str(
        cfg.get("api_key")
        or indexing_config.models.embedding_api_key
        or ""
    ).strip()
    model = str(cfg.get("model") or indexing_config.models.embedding_model or "text-embedding-3-large")
    model = normalize_embedding_model(model, base_url=base_url)
    if base_url and api_key:
        url = f"{base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json={
                    "model": model,
                    "input": [str(text or "None") for text in texts],
                },
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data", [])
        vectors = [item.get("embedding", []) for item in data]
        if len(vectors) != len(texts):
            raise RuntimeError("embedding response size mismatch")
        return vectors

    dimension = int(cfg.get("dimension", 16))
    vectors: list[list[float]] = []
    for text in texts:
        seed = f"{model}:{text}".encode("utf-8")
        values = [(seed[index % len(seed)] if seed else 0) / 255.0 for index in range(dimension)]
        vectors.append(values)
    return vectors


class NoopIndexBackend:
    async def write_bundle(self, bundle) -> dict[str, int]:
        return {
            "opensearch_record_count": len(bundle.opensearch_records),
            "qdrant_point_count": len(bundle.qdrant_points),
        }


class OpenSearchIndexWriter:
    def __init__(self, *, base_url: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def write_records(self, records: list[dict[str, object]]) -> int:
        if not records:
            return 0
        index_names = {str(record["index_name"]) for record in records}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for index_name in sorted(index_names):
                response = await client.put(
                    f"{self.base_url}/{index_name}",
                    json={},
                )
                if response.status_code not in (200, 201):
                    response.raise_for_status()
            payload_lines: list[str] = []
            for record in records:
                payload_lines.append(
                    f'{{"index":{{"_index":"{record["index_name"]}","_id":"{record["document_id"]}"}}}}'
                )
                payload_lines.append(_json_dump(record["body"]))
            response = await client.post(
                f"{self.base_url}/_bulk",
                content="\n".join(payload_lines) + "\n",
                headers={"Content-Type": "application/x-ndjson"},
            )
            response.raise_for_status()
            data = response.json()
            if data.get("errors"):
                raise RuntimeError("OpenSearch bulk indexing reported errors")
        return len(records)


class QdrantPointWriter:
    def __init__(self, *, base_url: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def write_points(self, collection_name: str, points: list[dict[str, object]]) -> int:
        if not points:
            return 0
        title_texts = [str(point.get("payload", {}).get("title_text", "") or "Title") for point in points]
        body_texts = [str(point.get("payload", {}).get("embedding_text", "") or "None") for point in points]
        weights = [
            float(point.get("payload", {}).get("embedding_title_weight", 0.1) or 0.1)
            for point in points
        ]
        title_vectors = await embed_texts(
            title_texts,
            config={"model": load_indexing_config().models.embedding_model},
        )
        body_vectors = await embed_texts(
            body_texts,
            config={"model": load_indexing_config().models.embedding_model},
        )
        vectors = [
            _mix_vectors(title_vector, body_vector, title_weight)
            for title_vector, body_vector, title_weight in zip(title_vectors, body_vectors, weights, strict=True)
        ]
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(
                f"{self.base_url}/collections/{collection_name}",
                json={"vectors": {"size": len(vectors[0]) if vectors else 16, "distance": "Cosine"}},
            )
            if response.status_code not in (200, 201):
                response.raise_for_status()
            response = await client.put(
                f"{self.base_url}/collections/{collection_name}/points",
                json={
                    "points": [
                        {
                            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(point["point_id"]))),
                            "vector": vectors[index],
                            "payload": point["payload"],
                        }
                        for index, point in enumerate(points)
                    ]
                },
            )
            response.raise_for_status()
        return len(points)


class HybridIndexBackend:
    def __init__(
        self,
        *,
        opensearch_writer: OpenSearchIndexWriter,
        qdrant_writer: QdrantPointWriter,
    ) -> None:
        self._opensearch_writer = opensearch_writer
        self._qdrant_writer = qdrant_writer

    async def write_bundle(self, bundle) -> dict[str, int]:
        opensearch_count = await self._opensearch_writer.write_records(
            [record.model_dump(mode="json") for record in bundle.opensearch_records]
        )
        qdrant_count = await self._qdrant_writer.write_points(
            bundle.qdrant_points[0].collection_name if bundle.qdrant_points else "",
            [point.model_dump(mode="json") for point in bundle.qdrant_points],
        )
        return {
            "opensearch_record_count": opensearch_count,
            "qdrant_point_count": qdrant_count,
        }


def get_index_backend():
    config = load_indexing_config()
    mode = config.backend.mode
    if mode == "hybrid":
        opensearch_url = config.backend.opensearch_url
        qdrant_url = config.backend.qdrant_url
        if not opensearch_url or not qdrant_url:
            raise RuntimeError("hybrid backend requires INDEXING_OPENSEARCH_URL and INDEXING_QDRANT_URL")
        return HybridIndexBackend(
            opensearch_writer=OpenSearchIndexWriter(base_url=opensearch_url),
            qdrant_writer=QdrantPointWriter(base_url=qdrant_url),
        )
    return NoopIndexBackend()


def _json_dump(payload: object) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _mix_vectors(title_vector: list[float], body_vector: list[float], title_weight: float) -> list[float]:
    safe_weight = max(0.0, min(float(title_weight), 1.0))
    body_weight = 1.0 - safe_weight
    mixed: list[float] = []
    for title_value, body_value in zip_longest(title_vector, body_vector, fillvalue=0.0):
        mixed.append((safe_weight * float(title_value)) + (body_weight * float(body_value)))
    return mixed

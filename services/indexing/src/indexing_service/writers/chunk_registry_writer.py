from __future__ import annotations

from typing import Any


class ChunkRegistryWriter:
    def write(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for chunk in chunks:
            display_text = str(chunk.display_text if hasattr(chunk, "display_text") else chunk["display_text"]).strip()
            vector_text = str(chunk.vector_text if hasattr(chunk, "vector_text") else chunk["vector_text"]).strip()
            source_block_ids = chunk.source_block_ids if hasattr(chunk, "source_block_ids") else chunk["source_block_ids"]
            citation_payload = chunk.citation_payload if hasattr(chunk, "citation_payload") else chunk["citation_payload"]
            if not display_text:
                raise ValueError("Chunk display_text must not be empty")
            if not vector_text:
                raise ValueError("Chunk vector_text must not be empty")
            if not source_block_ids:
                raise ValueError("Chunk source_block_ids must not be empty")
            if "anchor" not in citation_payload:
                raise ValueError("Chunk citation_payload must include anchor")
        return chunks

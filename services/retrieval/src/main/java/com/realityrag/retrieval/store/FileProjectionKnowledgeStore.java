package com.realityrag.retrieval.store;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.support.JsonProjectionReader;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

public class FileProjectionKnowledgeStore implements KnowledgeStore {
    private final Path chunksPath;
    private final ObjectMapper objectMapper;

    public FileProjectionKnowledgeStore(Path chunksPath, ObjectMapper objectMapper) {
        this.chunksPath = chunksPath;
        this.objectMapper = objectMapper;
    }

    @Override
    public List<IndexedChunk> listChunks(String collectionId) {
        return JsonProjectionReader.readJsonLines(chunksPath, objectMapper).stream()
            .map(this::toChunk)
            .filter(chunk -> chunk.collectionId().equals(collectionId))
            .toList();
    }

    @SuppressWarnings("unchecked")
    private IndexedChunk toChunk(Map<String, Object> parsed) {
        return new IndexedChunk(
            JsonProjectionReader.stringValue(parsed, "collection_id"),
            JsonProjectionReader.stringValue(parsed, "final_doc_id"),
            JsonProjectionReader.coalesce(parsed, "index_version_id", "active_index_version_id"),
            JsonProjectionReader.stringValue(parsed, "document_index_revision_id"),
            JsonProjectionReader.stringValue(parsed, "chunk_id"),
            JsonProjectionReader.stringValue(parsed, "display_text"),
            JsonProjectionReader.stringValue(parsed, "vector_text"),
            JsonProjectionReader.stringList(parsed.get("section_path")),
            JsonProjectionReader.pageSpans(parsed.get("page_spans")),
            JsonProjectionReader.stringValue(parsed, "published_document_state"),
            JsonProjectionReader.stringValue(parsed, "visibility"),
            JsonProjectionReader.stringList(parsed.get("allowed_principal_ids")),
            JsonProjectionReader.stringList(parsed.get("allowed_groups")),
            parsed.get("citation_payload") instanceof Map<?, ?> payload ? (Map<String, Object>) payload : Map.of(),
            parsed.get("metadata") instanceof Map<?, ?> metadata ? (Map<String, Object>) metadata : Map.of()
        );
    }
}

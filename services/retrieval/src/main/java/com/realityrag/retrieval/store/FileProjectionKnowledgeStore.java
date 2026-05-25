package com.realityrag.retrieval.store;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.contracts.KnowledgeContext;
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
            stringValue(parsed, "collection_id"),
            stringValue(parsed, "final_doc_id"),
            coalesce(parsed, "index_version_id", "active_index_version_id"),
            stringValue(parsed, "document_index_revision_id"),
            stringValue(parsed, "chunk_id"),
            stringValue(parsed, "display_text"),
            stringValue(parsed, "vector_text"),
            stringList(parsed.get("section_path")),
            pageSpans(parsed.get("page_spans")),
            stringValue(parsed, "published_document_state"),
            stringValue(parsed, "visibility"),
            stringList(parsed.get("allowed_principal_ids")),
            stringList(parsed.get("allowed_groups")),
            parsed.get("citation_payload") instanceof Map<?, ?> payload ? (Map<String, Object>) payload : Map.of(),
            parsed.get("metadata") instanceof Map<?, ?> metadata ? (Map<String, Object>) metadata : Map.of()
        );
    }

    private String stringValue(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        return value == null ? "" : String.valueOf(value);
    }

    private String coalesce(Map<String, Object> payload, String primary, String fallback) {
        String primaryValue = stringValue(payload, primary);
        return primaryValue.isBlank() ? stringValue(payload, fallback) : primaryValue;
    }

    @SuppressWarnings("unchecked")
    private List<String> stringList(Object raw) {
        if (raw == null) {
            return List.of();
        }
        return ((List<Object>) raw).stream().map(String::valueOf).toList();
    }

    @SuppressWarnings("unchecked")
    private List<KnowledgeContext.PageSpan> pageSpans(Object raw) {
        if (raw == null) {
            return List.of();
        }
        return ((List<Map<String, Object>>) raw).stream()
            .map(item -> new KnowledgeContext.PageSpan(
                intValue(item.get("page_from"), 1),
                intValue(item.get("page_to"), 1)
            ))
            .toList();
    }

    private int intValue(Object value, int defaultValue) {
        return value instanceof Number number ? number.intValue() : defaultValue;
    }
}

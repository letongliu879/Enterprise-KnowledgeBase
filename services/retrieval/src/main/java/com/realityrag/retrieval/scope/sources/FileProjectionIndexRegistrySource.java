package com.realityrag.retrieval.scope.sources;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.support.JsonProjectionReader;
import java.nio.file.Path;
import java.util.Map;
import java.util.Optional;

public class FileProjectionIndexRegistrySource implements IndexRegistrySource {
    private final Path indexRegistryPath;
    private final ObjectMapper objectMapper;

    public FileProjectionIndexRegistrySource(Path indexRegistryPath, ObjectMapper objectMapper) {
        this.indexRegistryPath = indexRegistryPath;
        this.objectMapper = objectMapper;
    }

    @Override
    public Optional<IndexRegistryRecord> findActiveIndex(String collectionId) {
        return JsonProjectionReader.readJsonLines(indexRegistryPath, objectMapper).stream()
            .filter(item -> collectionId.equals(stringValue(item, "collection_id")))
            .filter(item -> {
                String status = stringValue(item, "status");
                return status.isEmpty() || "ACTIVE".equalsIgnoreCase(status) || "INDEXED".equalsIgnoreCase(status);
            })
            .findFirst()
            .map(this::toRecord);
    }

    private IndexRegistryRecord toRecord(Map<String, Object> item) {
        return new IndexRegistryRecord(
            stringValue(item, "tenant_id"),
            stringValue(item, "collection_id"),
            coalesce(item, "index_version_id", "index_version"),
            stringValue(item, "opensearch_index"),
            stringValue(item, "qdrant_collection"),
            stringValue(item, "embedding_model"),
            stringValue(item, "chunk_profile_id")
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
}

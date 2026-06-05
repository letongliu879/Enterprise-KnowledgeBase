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
            .filter(item -> collectionId.equals(JsonProjectionReader.stringValue(item, "collection_id")))
            .filter(item -> {
                String status = JsonProjectionReader.stringValue(item, "status");
                return status.isEmpty() || "ACTIVE".equalsIgnoreCase(status) || "INDEXED".equalsIgnoreCase(status);
            })
            .findFirst()
            .map(this::toRecord);
    }

    private IndexRegistryRecord toRecord(Map<String, Object> item) {
        return new IndexRegistryRecord(
            JsonProjectionReader.stringValue(item, "tenant_id"),
            JsonProjectionReader.stringValue(item, "collection_id"),
            JsonProjectionReader.coalesce(item, "index_version_id", "index_version"),
            JsonProjectionReader.stringValue(item, "opensearch_index"),
            JsonProjectionReader.stringValue(item, "qdrant_collection"),
            JsonProjectionReader.stringValue(item, "embedding_model"),
            JsonProjectionReader.stringValue(item, "chunk_profile_id")
        );
    }
}

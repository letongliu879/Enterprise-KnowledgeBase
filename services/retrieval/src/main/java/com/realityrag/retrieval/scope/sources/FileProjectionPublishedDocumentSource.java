package com.realityrag.retrieval.scope.sources;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.support.JsonProjectionReader;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

public class FileProjectionPublishedDocumentSource implements PublishedDocumentSource {
    private final Path publishedDocumentsPath;
    private final ObjectMapper objectMapper;

    public FileProjectionPublishedDocumentSource(Path publishedDocumentsPath, ObjectMapper objectMapper) {
        this.publishedDocumentsPath = publishedDocumentsPath;
        this.objectMapper = objectMapper;
    }

    @Override
    public List<PublishedDocumentRecord> listByCollection(String collectionId) {
        return JsonProjectionReader.readJsonLines(publishedDocumentsPath, objectMapper).stream()
            .filter(item -> collectionId.equals(stringValue(item, "collection_id")))
            .map(this::toRecord)
            .toList();
    }

    private PublishedDocumentRecord toRecord(Map<String, Object> item) {
        return new PublishedDocumentRecord(
            stringValue(item, "collection_id"),
            stringValue(item, "final_doc_id"),
            stringValue(item, "published_document_state"),
            stringValue(item, "active_index_version_id"),
            stringValue(item, "visibility"),
            stringList(item.get("allowed_principal_ids")),
            stringList(item.get("allowed_groups"))
        );
    }

    private String stringValue(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        return value == null ? "" : String.valueOf(value);
    }

    @SuppressWarnings("unchecked")
    private List<String> stringList(Object raw) {
        if (raw == null) {
            return List.of();
        }
        return ((List<Object>) raw).stream().map(String::valueOf).toList();
    }
}

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
            .filter(item -> collectionId.equals(JsonProjectionReader.stringValue(item, "collection_id")))
            .map(this::toRecord)
            .toList();
    }

    private PublishedDocumentRecord toRecord(Map<String, Object> item) {
        return new PublishedDocumentRecord(
            JsonProjectionReader.stringValue(item, "collection_id"),
            JsonProjectionReader.stringValue(item, "final_doc_id"),
            JsonProjectionReader.stringValue(item, "published_document_state"),
            JsonProjectionReader.stringValue(item, "active_index_version_id"),
            JsonProjectionReader.stringValue(item, "visibility"),
            JsonProjectionReader.stringList(item.get("allowed_principal_ids")),
            JsonProjectionReader.stringList(item.get("allowed_groups"))
        );
    }
}

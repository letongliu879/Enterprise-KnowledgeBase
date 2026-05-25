package com.realityrag.retrieval.toc;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.support.JsonProjectionReader;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

public class FileProjectionDocumentTocSource implements DocumentTocSource {
    private final Path tocPath;
    private final ObjectMapper objectMapper;

    public FileProjectionDocumentTocSource(Path tocPath, ObjectMapper objectMapper) {
        this.tocPath = tocPath;
        this.objectMapper = objectMapper;
    }

    @Override
    public List<DocumentTocNode> listByDocument(String collectionId, String finalDocId) {
        return JsonProjectionReader.readJsonLines(tocPath, objectMapper).stream()
            .map(this::toNode)
            .filter(node -> node.collectionId().equals(collectionId))
            .filter(node -> node.finalDocId().equals(finalDocId))
            .toList();
    }

    @SuppressWarnings("unchecked")
    private DocumentTocNode toNode(Map<String, Object> payload) {
        return new DocumentTocNode(
            stringValue(payload, "collection_id"),
            stringValue(payload, "final_doc_id"),
            stringValue(payload, "toc_node_id"),
            stringValue(payload, "parent_toc_node_id"),
            stringValue(payload, "level"),
            stringValue(payload, "title"),
            payload.get("toc_path") instanceof List<?> tocPathValue
                ? tocPathValue.stream().map(String::valueOf).toList()
                : List.of(),
            payload.get("linked_chunk_ids") instanceof List<?> linkedChunkIds
                ? linkedChunkIds.stream().map(String::valueOf).toList()
                : List.of()
        );
    }

    private String stringValue(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        return value == null ? "" : String.valueOf(value);
    }
}

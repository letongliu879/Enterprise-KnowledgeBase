package com.realityrag.retrieval.store;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.contracts.KnowledgeContext;
import java.sql.Clob;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;

public class JdbcChunkRegistryKnowledgeStore implements KnowledgeStore {
    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public JdbcChunkRegistryKnowledgeStore(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @Override
    public List<IndexedChunk> listChunks(String collectionId) {
        return listChunks(collectionId, "");
    }

    @Override
    public List<IndexedChunk> listChunks(String collectionId, String indexVersionId) {
        boolean filterIndexVersion = indexVersionId != null && !indexVersionId.isBlank();
        return jdbcTemplate.query(
            filterIndexVersion ? """
                SELECT payload_json
                FROM chunk_registry
                WHERE collection_id = ?
                  AND index_version_id = ?
                  AND available_int = 1
                ORDER BY created_at
                """ : """
                SELECT payload_json
                FROM chunk_registry
                WHERE collection_id = ?
                  AND available_int = 1
                ORDER BY created_at
                """,
            (rs, rowNum) -> toChunk(parsePayload(rs.getObject("payload_json"))),
            filterIndexVersion ? new Object[] {collectionId, indexVersionId} : new Object[] {collectionId}
        );
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parsePayload(Object raw) throws SQLException {
        if (raw instanceof Map<?, ?> payload) {
            return (Map<String, Object>) payload;
        }
        if (raw == null) {
            return Map.of();
        }
        if (raw instanceof Clob clob) {
            return parseJson(clob.getSubString(1, Math.toIntExact(clob.length())));
        }
        return parseJson(String.valueOf(raw));
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseJson(String raw) throws SQLException {
        try {
            return objectMapper.readValue(raw, Map.class);
        }
        catch (Exception error) {
            throw new SQLException("Failed to parse chunk_registry.payload_json", error);
        }
    }

    @SuppressWarnings("unchecked")
    private IndexedChunk toChunk(Map<String, Object> parsed) {
        return new IndexedChunk(
            stringValue(parsed, "collection_id"),
            docIdValue(parsed),
            stringValue(parsed, "index_version_id"),
            stringValue(parsed, "document_index_revision_id"),
            stringValue(parsed, "chunk_id"),
            stringValue(parsed, "display_text"),
            stringValue(parsed, "vector_text"),
            stringList(parsed.get("section_path")),
            pageSpans(parsed.get("page_spans")),
            stringValue(parsed, "published_document_state"),
            stringValue(parsed, "visibility"),
            accessControlList(parsed, "allowed_principal_ids"),
            accessControlList(parsed, "allowed_groups"),
            parsed.get("citation_payload") instanceof Map<?, ?> payload ? (Map<String, Object>) payload : Map.of(),
            parsed.get("metadata") instanceof Map<?, ?> metadata ? (Map<String, Object>) metadata : Map.of()
        );
    }

    @SuppressWarnings("unchecked")
    private List<String> accessControlList(Map<String, Object> payload, String key) {
        Object topLevel = payload.get(key);
        if (topLevel instanceof List<?>) {
            return stringList(topLevel);
        }
        Object accessControl = payload.get("access_control");
        if (accessControl instanceof Map<?, ?> ac) {
            return stringList(ac.get(key));
        }
        return List.of();
    }

    private String docIdValue(Map<String, Object> payload) {
        String value = stringValue(payload, "final_doc_id");
        if (!value.isBlank()) {
            return value;
        }
        return stringValue(payload, "doc_id");
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

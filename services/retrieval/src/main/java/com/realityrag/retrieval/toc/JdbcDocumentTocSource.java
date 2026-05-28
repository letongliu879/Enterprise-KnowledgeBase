package com.realityrag.retrieval.toc;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.Clob;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;

public class JdbcDocumentTocSource implements DocumentTocSource {
    private static final TypeReference<List<Map<String, Object>>> OUTLINE_TYPE = new TypeReference<>() {};

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public JdbcDocumentTocSource(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @Override
    public List<DocumentTocNode> listByDocument(String collectionId, String finalDocId) {
        List<List<DocumentTocNode>> rows = jdbcTemplate.query(
            """
                SELECT outline
                FROM indexed_documents
                WHERE collection_id = ?
                  AND final_doc_id = ?
                  AND UPPER(state) IN ('ACTIVE', 'ACTIVATED')
                ORDER BY activated_at DESC, updated_at DESC
                LIMIT 1
                """,
            (rs, rowNum) -> parseOutline(rs),
            collectionId,
            finalDocId
        );
        return rows.stream().findFirst().orElse(List.of());
    }

    private List<DocumentTocNode> parseOutline(ResultSet rs) throws SQLException {
        Object raw = rs.getObject("outline");
        if (raw == null) {
            return List.of();
        }
        String json = raw instanceof Clob clob ? clob.getSubString(1, Math.toIntExact(clob.length())) : String.valueOf(raw);
        if (json.isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(json, OUTLINE_TYPE).stream()
                .map(this::toNode)
                .toList();
        }
        catch (Exception error) {
            throw new SQLException("Failed to parse indexed_documents.outline", error);
        }
    }

    private DocumentTocNode toNode(Map<String, Object> item) {
        String id = stringValue(item, "id", stringValue(item, "toc_id", ""));
        String title = stringValue(item, "title", stringValue(item, "heading", ""));
        return new DocumentTocNode(
            stringValue(item, "collection_id", ""),
            stringValue(item, "final_doc_id", ""),
            id,
            stringValue(item, "parent_toc_node_id", ""),
            String.valueOf(intValue(item.get("level"), 1)),
            title,
            stringList(item.get("toc_path")),
            stringList(item.get("linked_chunk_ids"))
        );
    }

    private String stringValue(Map<String, Object> item, String key, String defaultValue) {
        Object value = item.get(key);
        return value == null ? defaultValue : String.valueOf(value);
    }

    private int intValue(Object value, int defaultValue) {
        return value instanceof Number number ? number.intValue() : defaultValue;
    }

    @SuppressWarnings("unchecked")
    private List<String> stringList(Object raw) {
        if (raw == null) {
            return List.of();
        }
        if (raw instanceof List<?> values) {
            return values.stream().map(String::valueOf).toList();
        }
        return List.of(String.valueOf(raw));
    }
}

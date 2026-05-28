package com.realityrag.retrieval.scope.sources;

import java.util.List;
import java.util.Locale;
import org.springframework.jdbc.core.JdbcTemplate;

public class JdbcPublishedDocumentSource implements PublishedDocumentSource {
    private final JdbcTemplate jdbcTemplate;

    public JdbcPublishedDocumentSource(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public List<PublishedDocumentRecord> listByCollection(String collectionId) {
        return jdbcTemplate.query(
            """
                SELECT collection_id, final_doc_id, state, active_index_version
                FROM published_documents
                WHERE collection_id = ?
                ORDER BY created_at
                """,
            (rs, rowNum) -> new PublishedDocumentRecord(
                rs.getString("collection_id"),
                rs.getString("final_doc_id"),
                normalizeState(rs.getString("state")),
                rs.getString("active_index_version"),
                "internal",
                List.of(),
                List.of()
            ),
            collectionId
        );
    }

    private String normalizeState(String state) {
        if (state == null || state.isBlank()) {
            return "";
        }
        return state.trim().toUpperCase(Locale.ROOT);
    }
}

package com.realityrag.retrieval.scope.sources;

import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;

public class JdbcIndexRegistrySource implements IndexRegistrySource {
    private final JdbcTemplate jdbcTemplate;

    public JdbcIndexRegistrySource(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public Optional<IndexRegistryRecord> findActiveIndex(String collectionId) {
        return jdbcTemplate.query(
            """
                SELECT
                    COALESCE(v.tenant_id, '') AS tenant_id,
                    r.collection_id,
                    r.index_version,
                    COALESCE(v.opensearch_index, '') AS opensearch_index,
                    COALESCE(v.qdrant_collection, '') AS qdrant_collection,
                    COALESCE(v.embedding_model, '') AS embedding_model,
                    COALESCE(v.chunk_profile_id, '') AS chunk_profile_id
                FROM index_registry r
                LEFT JOIN index_versions v ON v.index_version_id = r.index_version
                WHERE r.collection_id = ?
                  AND LOWER(COALESCE(r.status, '')) IN ('indexed', 'indexing', 'active')
                """,
            (rs, rowNum) -> new IndexRegistryRecord(
                rs.getString("tenant_id"),
                rs.getString("collection_id"),
                rs.getString("index_version"),
                rs.getString("opensearch_index"),
                rs.getString("qdrant_collection"),
                rs.getString("embedding_model"),
                rs.getString("chunk_profile_id")
            ),
            collectionId
        ).stream().findFirst();
    }
}

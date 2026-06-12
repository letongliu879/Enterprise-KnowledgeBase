package com.realityrag.retrieval.api;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.contracts.IndexProjectionSyncRequest;
import com.realityrag.retrieval.contracts.IndexProjectionSyncResponse;
import jakarta.annotation.PostConstruct;
import jakarta.validation.Valid;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class IndexProjectionSyncController {
    private static final Logger LOG = LoggerFactory.getLogger(IndexProjectionSyncController.class);

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public IndexProjectionSyncController(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @PostConstruct
    void validateSchema() {
        List<String> requiredTables = List.of(
            "index_projection_idempotency", "index_versions", "index_registry", "published_documents", "chunk_registry"
        );
        List<String> missing = requiredTables.stream()
            .filter(name -> !_tableExists(name))
            .toList();
        if (!missing.isEmpty()) {
            throw new IllegalStateException(
                "Required retrieval projection tables are missing: " + missing +
                ". Run 'uv run alembic -c packages/persistence/migrations/alembic.ini upgrade head' before starting the retrieval service."
            );
        }
    }

    private boolean _tableExists(String tableName) {
        try {
            jdbcTemplate.queryForObject(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1",
                Integer.class,
                tableName
            );
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @PostMapping("/internal/index-projections/sync")
    public ResponseEntity<IndexProjectionSyncResponse> syncProjection(
        @Valid @RequestBody IndexProjectionSyncRequest request
    ) {
        // Idempotency check
        boolean alreadyProcessed = checkIdempotency(request.idempotencyKey());
        if (alreadyProcessed) {
            return ResponseEntity.ok(new IndexProjectionSyncResponse(Instant.now().toString(), 0, 0));
        }

        try {
            var payload = request.payload();
            int chunksSynced = 0;
            int chunksRemoved = 0;

            if ("full_replace".equals(payload.syncMode())) {
                // Upsert index registry and published document metadata
                upsertIndexVersion(payload);
                upsertIndexRegistry(payload);
                upsertPublishedDocument(payload);

                // Delete existing chunks for this collection + version
                int removed = jdbcTemplate.update(
                    "DELETE FROM chunk_registry WHERE collection_id = ? AND index_version_id = ?",
                    payload.collectionId(),
                    payload.indexVersionId()
                );
                chunksRemoved = removed;

                // Insert new chunks
                List<Map<String, Object>> chunks = payload.chunks();
                if (chunks != null) {
                    for (Map<String, Object> chunk : chunks) {
                        insertChunk(payload.collectionId(), payload.indexVersionId(), chunk);
                        chunksSynced++;
                    }
                }
            } else if ("lifecycle_patch".equals(payload.syncMode())) {
                int availableInt = payload.availableInt() != null
                    ? payload.availableInt()
                    : ("PUBLISHED".equals(payload.lifecycleState()) ? 1 : 0);

                // Update available_int column
                int updated = jdbcTemplate.update(
                    "UPDATE chunk_registry SET available_int = ? WHERE collection_id = ? AND index_version_id = ? AND final_doc_id = ?",
                    availableInt,
                    payload.collectionId(),
                    payload.indexVersionId(),
                    payload.docId()
                );
                chunksSynced = updated;

                // Update published_document_state inside payload_json
                if (payload.lifecycleState() != null) {
                    updateLifecycleStateInPayload(
                        payload.collectionId(),
                        payload.indexVersionId(),
                        payload.docId(),
                        payload.lifecycleState()
                    );
                }
            }

            recordIdempotency(request.idempotencyKey());

            return ResponseEntity.ok(
                new IndexProjectionSyncResponse(Instant.now().toString(), chunksSynced, chunksRemoved)
            );
        } catch (DataAccessException error) {
            LOG.error("Index projection sync failed for collection={} indexVersion={} docId={}",
                request.payload() != null ? request.payload().collectionId() : null,
                request.payload() != null ? request.payload().indexVersionId() : null,
                request.payload() != null ? request.payload().docId() : null,
                error);
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new IndexProjectionSyncResponse(null, 0, 0));
        }
    }

    private void insertChunk(String collectionId, String indexVersionId, Map<String, Object> chunk) {
        String chunkId = String.valueOf(chunk.get("chunk_id"));
        String tenantId = String.valueOf(chunk.getOrDefault("tenant_id", ""));
        String docId = String.valueOf(chunk.getOrDefault("doc_id", ""));
        String documentIndexRevisionId = String.valueOf(chunk.getOrDefault("document_index_revision_id", ""));
        String chunkType = String.valueOf(chunk.getOrDefault("chunk_type", "text"));
        String displayText = String.valueOf(chunk.getOrDefault("display_text", ""));
        String vectorText = String.valueOf(chunk.getOrDefault("vector_text", ""));
        List<String> sectionPath = listValue(chunk.get("section_path"));
        List<Map<String, Object>> pageSpans = pageSpansValue(chunk.get("page_spans"));
        List<String> sourceBlockIds = listValue(chunk.get("source_block_ids"));
        List<String> keywordTerms = listValue(chunk.get("keyword_terms"));
        List<String> confirmedTags = listValue(chunk.get("confirmed_tags"));
        String visibility = String.valueOf(chunk.getOrDefault("visibility", "internal"));
        String publishedDocumentState = String.valueOf(chunk.getOrDefault("published_document_state", "PUBLISHED"));
        Map<String, Object> accessControl = mapValue(chunk.get("access_control"));
        Map<String, Object> citationPayload = mapValue(chunk.get("citation_payload"));
        Map<String, Object> lexicalPayload = mapValue(chunk.get("lexical_payload"));
        Map<String, Object> vectorPayload = mapValue(chunk.get("vector_payload"));
        Map<String, Object> metadata = mapValue(chunk.get("metadata"));
        String chunkHash = String.valueOf(chunk.getOrDefault("chunk_hash", ""));
        int availableInt = chunk.get("available_int") instanceof Number n ? n.intValue() : 1;

        // Build the payload_json as a single JSON object containing all chunk fields
        Map<String, Object> payload = Map.ofEntries(
            Map.entry("tenant_id", tenantId),
            Map.entry("collection_id", collectionId),
            Map.entry("final_doc_id", docId),
            Map.entry("index_version_id", indexVersionId),
            Map.entry("document_index_revision_id", documentIndexRevisionId),
            Map.entry("chunk_id", chunkId),
            Map.entry("chunk_type", chunkType),
            Map.entry("display_text", displayText),
            Map.entry("vector_text", vectorText),
            Map.entry("section_path", sectionPath),
            Map.entry("page_spans", pageSpans),
            Map.entry("source_block_ids", sourceBlockIds),
            Map.entry("keyword_terms", keywordTerms),
            Map.entry("confirmed_tags", confirmedTags),
            Map.entry("visibility", visibility),
            Map.entry("published_document_state", publishedDocumentState),
            Map.entry("access_control", accessControl),
            Map.entry("citation_payload", citationPayload),
            Map.entry("lexical_payload", lexicalPayload),
            Map.entry("vector_payload", vectorPayload),
            Map.entry("metadata", metadata),
            Map.entry("chunk_hash", chunkHash)
        );

        String payloadJson;
        try {
            payloadJson = objectMapper.writeValueAsString(sanitizeForJson(payload));
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Failed to serialize chunk payload", e);
        }

        jdbcTemplate.update(
            """
            INSERT INTO chunk_registry (
                chunk_id, tenant_id, collection_id, final_doc_id, index_version_id,
                available_int, visibility, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?::json, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            chunkId, tenantId, collectionId, docId, indexVersionId,
            availableInt, visibility, payloadJson
        );
    }

    @SuppressWarnings("unchecked")
    private void updateLifecycleStateInPayload(String collectionId, String indexVersionId, String docId, String lifecycleState) {
        List<String> chunkIds = jdbcTemplate.query(
            "SELECT chunk_id, payload_json FROM chunk_registry WHERE collection_id = ? AND index_version_id = ? AND final_doc_id = ?",
            (rs, rowNum) -> rs.getString("chunk_id"),
            collectionId, indexVersionId, docId
        );

        for (String chunkId : chunkIds) {
            String payloadJson = jdbcTemplate.queryForObject(
                "SELECT payload_json FROM chunk_registry WHERE chunk_id = ?",
                String.class,
                chunkId
            );
            if (payloadJson != null) {
                try {
                    Map<String, Object> payload = objectMapper.readValue(payloadJson, Map.class);
                    payload = new java.util.HashMap<>(payload);
                    payload.put("published_document_state", lifecycleState);
                    String updatedJson = objectMapper.writeValueAsString(payload);
                    jdbcTemplate.update(
                        "UPDATE chunk_registry SET payload_json = ?::json WHERE chunk_id = ?",
                        updatedJson, chunkId
                    );
                } catch (JsonProcessingException e) {
                    throw new IllegalStateException("Failed to update payload_json for " + chunkId, e);
                }
            }
        }
    }

    @SuppressWarnings("unchecked")
    private Object sanitizeForJson(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> sanitized = new java.util.LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String key = String.valueOf(entry.getKey());
                sanitized.put(key, sanitizeForJson(entry.getValue()));
            }
            return sanitized;
        }
        if (value instanceof List<?> list) {
            List<Object> sanitized = new java.util.ArrayList<>();
            for (Object item : list) {
                sanitized.add(sanitizeForJson(item));
            }
            return sanitized;
        }
        if (value instanceof Double d) {
            return Double.isFinite(d) ? d : null;
        }
        if (value instanceof Float f) {
            return Float.isFinite(f) ? f : null;
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    private List<String> listValue(Object raw) {
        if (raw instanceof List<?>) {
            return ((List<Object>) raw).stream().map(String::valueOf).toList();
        }
        return List.of();
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> pageSpansValue(Object raw) {
        if (raw instanceof List<?>) {
            return ((List<Object>) raw).stream()
                .filter(item -> item instanceof Map)
                .map(item -> (Map<String, Object>) item)
                .toList();
        }
        return List.of();
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> mapValue(Object raw) {
        if (raw instanceof Map<?, ?>) {
            return (Map<String, Object>) raw;
        }
        return Map.of();
    }

    private boolean checkIdempotency(String idempotencyKey) {
        List<String> results = jdbcTemplate.query(
            "SELECT idempotency_key FROM index_projection_idempotency WHERE idempotency_key = ?",
            (rs, rowNum) -> rs.getString("idempotency_key"),
            idempotencyKey
        );
        return !results.isEmpty();
    }

    private void recordIdempotency(String idempotencyKey) {
        jdbcTemplate.update(
            "INSERT INTO index_projection_idempotency (idempotency_key, processed_at) VALUES (?, ?)",
            idempotencyKey, Timestamp.from(Instant.now())
        );
    }

    private void upsertIndexVersion(IndexProjectionSyncRequest.IndexProjectionPayload payload) {
        if (payload.indexVersionId() == null) {
            return;
        }
        int updated = jdbcTemplate.update("""
            UPDATE index_versions SET
                tenant_id = ?, collection_id = ?, status = ?, schema_version = ?,
                index_profile_id = ?, chunk_profile_id = ?, embedding_model = ?,
                opensearch_index = ?, qdrant_collection = ?, chunk_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE index_version_id = ?
            """,
            payload.tenantId() != null ? payload.tenantId() : "",
            payload.collectionId(),
            "READY",
            payload.schemaVersion() != null ? payload.schemaVersion() : "v1",
            payload.indexProfileId() != null ? payload.indexProfileId() : "",
            payload.chunkProfileId() != null ? payload.chunkProfileId() : "",
            payload.embeddingModel() != null ? payload.embeddingModel() : "",
            payload.opensearchIndex() != null ? payload.opensearchIndex() : "",
            payload.qdrantCollection() != null ? payload.qdrantCollection() : "",
            payload.chunks() != null ? payload.chunks().size() : 0,
            payload.indexVersionId()
        );
        if (updated == 0) {
            jdbcTemplate.update("""
                INSERT INTO index_versions (
                    index_version_id, tenant_id, collection_id, status, schema_version,
                    index_profile_id, chunk_profile_id, embedding_model, opensearch_index,
                    qdrant_collection, chunk_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                payload.indexVersionId(),
                payload.tenantId() != null ? payload.tenantId() : "",
                payload.collectionId(),
                "indexed",
                payload.schemaVersion() != null ? payload.schemaVersion() : "v1",
                payload.indexProfileId() != null ? payload.indexProfileId() : "",
                payload.chunkProfileId() != null ? payload.chunkProfileId() : "",
                payload.embeddingModel() != null ? payload.embeddingModel() : "",
                payload.opensearchIndex() != null ? payload.opensearchIndex() : "",
                payload.qdrantCollection() != null ? payload.qdrantCollection() : "",
                payload.chunks() != null ? payload.chunks().size() : 0
            );
        }
    }

    private void upsertIndexRegistry(IndexProjectionSyncRequest.IndexProjectionPayload payload) {
        if (payload.collectionId() == null || payload.indexVersionId() == null) {
            return;
        }
        int updated = jdbcTemplate.update("""
            UPDATE index_registry SET
                index_version = ?, previous_index_version = ?, target_index_version = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE collection_id = ?
            """,
            payload.indexVersionId(),
            null,
            payload.indexVersionId(),
            "indexed",
            payload.collectionId()
        );
        if (updated == 0) {
            jdbcTemplate.update("""
                INSERT INTO index_registry (
                    collection_id, index_version, previous_index_version, target_index_version, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                payload.collectionId(),
                payload.indexVersionId(),
                null,
                payload.indexVersionId(),
                "indexed"
            );
        }
    }

    private void upsertPublishedDocument(IndexProjectionSyncRequest.IndexProjectionPayload payload) {
        if (payload.collectionId() == null || payload.docId() == null) {
            return;
        }
        String docId = payload.docId();
        String state = payload.publishedDocumentState() != null ? payload.publishedDocumentState() : "published";
        String publishedDocId = "pd_" + docId;
        jdbcTemplate.update("""
            INSERT INTO published_documents (
                published_document_id, final_doc_id, logical_document_id, tenant_id, collection_id,
                version, source_content_hash, canonical_hash, state, active_index_version,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (final_doc_id) DO UPDATE SET
                logical_document_id = EXCLUDED.logical_document_id,
                tenant_id = EXCLUDED.tenant_id,
                collection_id = EXCLUDED.collection_id,
                version = EXCLUDED.version,
                source_content_hash = EXCLUDED.source_content_hash,
                canonical_hash = EXCLUDED.canonical_hash,
                state = EXCLUDED.state,
                active_index_version = EXCLUDED.active_index_version,
                updated_at = CURRENT_TIMESTAMP
            """,
            publishedDocId,
            docId,
            docId,
            payload.tenantId() != null ? payload.tenantId() : "",
            payload.collectionId(),
            1,
            "",
            "",
            state,
            payload.indexVersionId() != null ? payload.indexVersionId() : ""
        );
    }
}

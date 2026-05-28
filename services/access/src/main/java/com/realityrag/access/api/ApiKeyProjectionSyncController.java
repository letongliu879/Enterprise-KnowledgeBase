package com.realityrag.access.api;

import com.realityrag.access.contracts.ApiKeyProjectionSyncRequest;
import com.realityrag.access.contracts.ApiKeyProjectionSyncResponse;
import jakarta.validation.Valid;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ApiKeyProjectionSyncController {

    private final JdbcTemplate jdbcTemplate;

    public ApiKeyProjectionSyncController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @PostMapping("/internal/api-key-projections/sync")
    public ResponseEntity<ApiKeyProjectionSyncResponse> syncProjection(
        @Valid @RequestBody ApiKeyProjectionSyncRequest request
    ) {
        ensureProjectionTableExists();
        ensureIdempotencyTableExists();

        // Idempotency check
        boolean alreadyProcessed = checkIdempotency(request.idempotencyKey());
        if (alreadyProcessed) {
            try {
                Instant syncedAt = jdbcTemplate.queryForObject(
                    "SELECT synced_at FROM api_key_projection WHERE api_key_id = ?",
                    Instant.class,
                    request.payload().apiKeyId()
                );
                return ResponseEntity.ok(new ApiKeyProjectionSyncResponse(syncedAt, true));
            } catch (EmptyResultDataAccessException e) {
                // Idempotency key exists but projection row is missing (partial write).
                // Fall through to re-process.
            }
        }

        try {
            upsertProjection(request);
            recordIdempotency(request.idempotencyKey());

            Instant syncedAt = Instant.now();
            jdbcTemplate.update(
                "UPDATE api_key_projection SET synced_at = ?, runtime_synced = TRUE WHERE api_key_id = ?",
                ts(syncedAt),
                request.payload().apiKeyId()
            );

            return ResponseEntity.ok(new ApiKeyProjectionSyncResponse(syncedAt, true));
        } catch (DataAccessException error) {
            error.printStackTrace();
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ApiKeyProjectionSyncResponse(null, false));
        }
    }

    private void ensureProjectionTableExists() {
        jdbcTemplate.execute("""
            CREATE TABLE IF NOT EXISTS api_key_projection (
                api_key_id VARCHAR(128) PRIMARY KEY,
                tenant_id VARCHAR(64) NOT NULL,
                agent_type_id VARCHAR(128) NOT NULL,
                knowledge_scopes VARCHAR(2048),
                roles VARCHAR(2048),
                debug_permission BOOLEAN NOT NULL DEFAULT FALSE,
                token_budget_limit INTEGER NOT NULL DEFAULT 4096,
                state VARCHAR(32) NOT NULL DEFAULT 'active',
                expires_at TIMESTAMP,
                projection_version INTEGER NOT NULL DEFAULT 1,
                last_updated_at TIMESTAMP NOT NULL,
                synced_at TIMESTAMP,
                runtime_synced BOOLEAN NOT NULL DEFAULT FALSE
            )
            """);
    }

    private void ensureIdempotencyTableExists() {
        jdbcTemplate.execute("""
            CREATE TABLE IF NOT EXISTS api_key_projection_idempotency (
                idempotency_key VARCHAR(256) PRIMARY KEY,
                processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """);
    }

    private boolean checkIdempotency(String idempotencyKey) {
        List<String> results = jdbcTemplate.query(
            "SELECT idempotency_key FROM api_key_projection_idempotency WHERE idempotency_key = ?",
            (rs, rowNum) -> rs.getString("idempotency_key"),
            idempotencyKey
        );
        return !results.isEmpty();
    }

    private void recordIdempotency(String idempotencyKey) {
        try {
            jdbcTemplate.update(
                "INSERT INTO api_key_projection_idempotency (idempotency_key, processed_at) VALUES (?, ?)",
                idempotencyKey, ts(Instant.now())
            );
        } catch (DataIntegrityViolationException e) {
            // already recorded, safe to ignore
        }
    }

    private void upsertProjection(ApiKeyProjectionSyncRequest request) {
        var payload = request.payload();
        int updated = jdbcTemplate.update("""
            UPDATE api_key_projection SET
                tenant_id = ?, agent_type_id = ?, knowledge_scopes = ?, roles = ?,
                debug_permission = ?, token_budget_limit = ?, state = ?, expires_at = ?,
                projection_version = ?, last_updated_at = ?, synced_at = ?, runtime_synced = ?
            WHERE api_key_id = ?
            """,
            payload.tenantId(),
            payload.agentTypeId(),
            json(payload.knowledgeScopes()),
            json(payload.roles()),
            payload.debugPermission(),
            payload.tokenBudgetLimit(),
            payload.state(),
            ts(payload.expiresAt()),
            payload.projectionVersion(),
            ts(payload.lastUpdatedAt()),
            ts(Instant.now()),
            false,
            payload.apiKeyId()
        );
        if (updated == 0) {
            jdbcTemplate.update("""
                INSERT INTO api_key_projection (
                    api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                    debug_permission, token_budget_limit, state, expires_at,
                    projection_version, last_updated_at, synced_at, runtime_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload.apiKeyId(),
                payload.tenantId(),
                payload.agentTypeId(),
                json(payload.knowledgeScopes()),
                json(payload.roles()),
                payload.debugPermission(),
                payload.tokenBudgetLimit(),
                payload.state(),
                ts(payload.expiresAt()),
                payload.projectionVersion(),
                ts(payload.lastUpdatedAt()),
                ts(Instant.now()),
                false
            );
        }
    }

    private String json(List<String> list) {
        if (list == null || list.isEmpty()) {
            return "[]";
        }
        try {
            return new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(list);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to serialize list to JSON", e);
        }
    }

    private static Timestamp ts(Instant instant) {
        return instant == null ? null : Timestamp.from(instant);
    }
}

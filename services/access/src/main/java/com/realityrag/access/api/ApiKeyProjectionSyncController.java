package com.realityrag.access.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.contracts.ApiKeyProjectionSyncRequest;
import com.realityrag.access.contracts.ApiKeyProjectionSyncResponse;
import jakarta.annotation.PostConstruct;
import jakarta.validation.Valid;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ApiKeyProjectionSyncController {
    private static final Logger log = LoggerFactory.getLogger(ApiKeyProjectionSyncController.class);

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;
    private final com.realityrag.access.security.ApiKeyRegistry apiKeyRegistry;

    public ApiKeyProjectionSyncController(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper, com.realityrag.access.security.ApiKeyRegistry apiKeyRegistry) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.apiKeyRegistry = apiKeyRegistry;
    }

    @PostConstruct
    void validateSchema() {
        if (!_tableExists("api_key_projection") || !_tableExists("api_key_projection_idempotency")) {
            throw new IllegalStateException(
                "Required API key projection tables are missing. Run 'uv run alembic -c packages/persistence/migrations/alembic.ini upgrade head' before starting the access service."
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

    @Transactional
    @PostMapping("/internal/api-key-projections/sync")
    public ResponseEntity<ApiKeyProjectionSyncResponse> syncProjection(
        @Valid @RequestBody ApiKeyProjectionSyncRequest request
    ) {
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
            mergeProjection(request);
            mergeIdempotency(request.idempotencyKey());
            String apiKeyId = request.payload().apiKeyId();
            if (TransactionSynchronizationManager.isSynchronizationActive()) {
                TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                    @Override
                    public void afterCommit() {
                        apiKeyRegistry.invalidateCache(apiKeyId);
                    }
                });
            } else {
                apiKeyRegistry.invalidateCache(apiKeyId);
            }

            Instant syncedAt = Instant.now();
            return ResponseEntity.ok(new ApiKeyProjectionSyncResponse(syncedAt, true));
        } catch (DataAccessException error) {
            log.error("Failed to sync API key projection for {}", request.payload().apiKeyId(), error);
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ApiKeyProjectionSyncResponse(null, false));
        }
    }

    private boolean checkIdempotency(String idempotencyKey) {
        List<String> results = jdbcTemplate.query(
            "SELECT idempotency_key FROM api_key_projection_idempotency WHERE idempotency_key = ?",
            (rs, rowNum) -> rs.getString("idempotency_key"),
            idempotencyKey
        );
        return !results.isEmpty();
    }

    private void mergeIdempotency(String idempotencyKey) {
        int updated = jdbcTemplate.update(
            "UPDATE api_key_projection_idempotency SET processed_at = ? WHERE idempotency_key = ?",
            ts(Instant.now()), idempotencyKey
        );
        if (updated == 0) {
            jdbcTemplate.update(
                "INSERT INTO api_key_projection_idempotency (idempotency_key, processed_at) VALUES (?, ?)",
                idempotencyKey, ts(Instant.now())
            );
        }
    }

    private void mergeProjection(ApiKeyProjectionSyncRequest request) {
        var payload = request.payload();
        int updated = jdbcTemplate.update(
            """
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
            true,
            payload.apiKeyId()
        );
        if (updated == 0) {
            jdbcTemplate.update(
                """
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
                true
            );
        }
    }

    private String json(List<String> list) {
        if (list == null || list.isEmpty()) {
            return "[]";
        }
        try {
            return objectMapper.writeValueAsString(list);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to serialize list to JSON", e);
        }
    }

    private static Timestamp ts(Instant instant) {
        return instant == null ? null : Timestamp.from(instant);
    }
}

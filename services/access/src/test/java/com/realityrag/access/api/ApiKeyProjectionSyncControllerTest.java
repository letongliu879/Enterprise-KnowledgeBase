package com.realityrag.access.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.AbstractPostgresTestBase;
import com.realityrag.access.contracts.ApiKeyProjection;
import com.realityrag.access.contracts.ApiKeyProjectionSyncRequest;
import com.realityrag.access.security.ApiKeyRegistry;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class ApiKeyProjectionSyncControllerTest extends AbstractPostgresTestBase {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void successfulSyncUpsertsProjection() throws Exception {
        var payload = new ApiKeyProjection(
            "key-sync-test",
            "tnt_default",
            "kb_assistant",
            List.of("col_policy"),
            List.of("agent"),
            false,
            4096,
            "active",
            null,
            1,
            Instant.now()
        );
        var request = new ApiKeyProjectionSyncRequest(
            "cmd-001", "trc-001", "idem-001", "admin_service",
            "tnt_default", "api_key_projection", "key-sync-test",
            payload
        );

        mockMvc.perform(post("/internal/api-key-projections/sync")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.runtime_synced").value(true));
    }

    @Test
    void duplicateSyncIsIdempotent() throws Exception {
        var payload = new ApiKeyProjection(
            "key-idempotent",
            "tnt_default",
            "kb_assistant",
            List.of("col_policy"),
            List.of("agent"),
            false,
            4096,
            "active",
            null,
            1,
            Instant.now()
        );
        var request = new ApiKeyProjectionSyncRequest(
            "cmd-002", "trc-002", "idem-idempotent", "admin_service",
            "tnt_default", "api_key_projection", "key-idempotent",
            payload
        );

        // First sync
        mockMvc.perform(post("/internal/api-key-projections/sync")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.runtime_synced").value(true));

        // Second sync with same idempotency key
        mockMvc.perform(post("/internal/api-key-projections/sync")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.runtime_synced").value(true));
    }

    @Test
    void invalidPayloadReturnsBadRequest() throws Exception {
        String invalidJson = "{\"command_id\":\"cmd-003\"}";

        mockMvc.perform(post("/internal/api-key-projections/sync")
                .contentType(MediaType.APPLICATION_JSON)
                .content(invalidJson))
            .andExpect(status().isBadRequest());
    }

    @Test
    void syncInvalidatesCacheAfterCommit() throws Exception {
        var initialPayload = new ApiKeyProjection(
            "key-cache-invalidation",
            "tnt_default",
            "kb_assistant",
            List.of("col_policy"),
            List.of("agent"),
            false,
            4096,
            "active",
            null,
            1,
            Instant.now()
        );
        var initialRequest = new ApiKeyProjectionSyncRequest(
            "cmd-cache-001", "trc-cache-001", "idem-cache-001", "admin_service",
            "tnt_default", "api_key_projection", "key-cache-invalidation",
            initialPayload
        );

        mockMvc.perform(post("/internal/api-key-projections/sync")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(initialRequest)))
            .andExpect(status().isOk());

        ApiKeyRegistry registry = new ApiKeyRegistry(jdbcTemplate, objectMapper,
            new com.realityrag.access.config.AccessProperties(),
            new com.realityrag.access.security.NoOpApiKeyProjectionCache());
        var first = registry.resolve("key-cache-invalidation");
        assertNotNull(first);
        assertEquals(4096, first.maxContextTokens());

        var updatedPayload = new ApiKeyProjection(
            "key-cache-invalidation",
            "tnt_default",
            "kb_assistant",
            List.of("col_policy"),
            List.of("agent"),
            false,
            2048,
            "active",
            null,
            2,
            Instant.now()
        );
        var updatedRequest = new ApiKeyProjectionSyncRequest(
            "cmd-cache-002", "trc-cache-002", "idem-cache-002", "admin_service",
            "tnt_default", "api_key_projection", "key-cache-invalidation",
            updatedPayload
        );

        mockMvc.perform(post("/internal/api-key-projections/sync")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(updatedRequest)))
            .andExpect(status().isOk());

        var second = registry.resolve("key-cache-invalidation");
        assertNotNull(second);
        assertEquals(2048, second.maxContextTokens());
    }
}

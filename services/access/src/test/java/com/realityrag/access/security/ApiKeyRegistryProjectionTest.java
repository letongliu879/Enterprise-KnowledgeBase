package com.realityrag.access.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.realityrag.access.support.AccessException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

class ApiKeyRegistryProjectionTest {

    private JdbcTemplate jdbcTemplate;
    private ApiKeyRegistry registry;

    @BeforeEach
    void setUp() {
        var dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("org.h2.Driver");
        dataSource.setUrl("jdbc:h2:mem:access-registry-test;MODE=PostgreSQL;DB_CLOSE_DELAY=-1");
        dataSource.setUsername("sa");
        dataSource.setPassword("");

        jdbcTemplate = new JdbcTemplate(dataSource);
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
        jdbcTemplate.update("DELETE FROM api_key_projection");
        registry = new ApiKeyRegistry(jdbcTemplate, new ObjectMapper());
    }

    @Test
    void activeKeyResolvesSuccessfully() {
        insertProjection("key-active", "active", null, 4096, Instant.now());

        var reg = registry.resolve("key-active");
        assertNotNull(reg);
        assertEquals("key-active", reg.apiKeyId());
        assertEquals("tnt_default", reg.tenantId());
        assertEquals(4096, reg.maxContextTokens());
        assertEquals("active", reg.state());
    }

    @Test
    void disabledKeyFailsClosed() {
        insertProjection("key-disabled", "disabled", null, 4096, Instant.now());

        assertThrows(AccessException.Unauthenticated.class, () -> registry.resolve("key-disabled"));
    }

    @Test
    void revokedKeyFailsClosed() {
        insertProjection("key-revoked", "revoked", null, 4096, Instant.now());

        assertThrows(AccessException.Unauthenticated.class, () -> registry.resolve("key-revoked"));
    }

    @Test
    void expiredKeyFailsClosed() {
        Instant expired = Instant.now().minus(1, ChronoUnit.DAYS);
        insertProjection("key-expired", "active", expired, 4096, Instant.now());

        assertThrows(AccessException.Unauthenticated.class, () -> registry.resolve("key-expired"));
    }

    @Test
    void staleProjectionFailsClosed() {
        Instant stale = Instant.now().minus(2, ChronoUnit.HOURS);
        insertProjection("key-stale", "active", null, 4096, stale);

        assertThrows(AccessException.RegistryUnavailable.class, () -> registry.resolve("key-stale"));
    }

    @Test
    void tokenBudgetLimitMappedToMaxContextTokens() {
        insertProjection("key-budget", "active", null, 2048, Instant.now());

        var reg = registry.resolve("key-budget");
        assertNotNull(reg);
        assertEquals(2048, reg.maxContextTokens());
    }

    @Test
    void missingKeyReturnsNull() {
        var reg = registry.resolve("key-missing");
        assertNull(reg);
    }

    @Test
    void scopeAndRolesAndDebugPermissionAreConsumed() {
        jdbcTemplate.update(
            """
                INSERT INTO api_key_projection (
                    api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                    debug_permission, token_budget_limit, state, expires_at,
                    projection_version, last_updated_at, runtime_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            "key-full", "tnt_default", "kb_assistant",
            "[\"col_policy\",\"col_handbook\"]",
            "[\"agent\",\"developer\"]",
            true, 8192, "active", null, 1, Instant.now(), true
        );

        var reg = registry.resolve("key-full");
        assertNotNull(reg);
        assertEquals(2, reg.knowledgeScopes().size());
        assertEquals(2, reg.roles().size());
        assertEquals(true, reg.debugPermission());
    }

    private void insertProjection(String apiKeyId, String state, Instant expiresAt, int budget, Instant lastUpdated) {
        jdbcTemplate.update(
            """
                INSERT INTO api_key_projection (
                    api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                    debug_permission, token_budget_limit, state, expires_at,
                    projection_version, last_updated_at, runtime_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            apiKeyId, "tnt_default", "kb_assistant", "[]", "[]",
            false, budget, state, expiresAt, 1, lastUpdated, true
        );
    }
}

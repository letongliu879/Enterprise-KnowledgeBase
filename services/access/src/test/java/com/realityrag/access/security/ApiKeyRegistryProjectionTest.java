package com.realityrag.access.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.realityrag.access.support.AccessException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

@Testcontainers
class ApiKeyRegistryProjectionTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    private static javax.sql.DataSource sharedDataSource;

    private JdbcTemplate jdbcTemplate;
    private ApiKeyRegistry registry;

    @BeforeAll
    static void beforeAll() throws Exception {
        var config = new HikariConfig();
        config.setJdbcUrl(postgres.getJdbcUrl());
        config.setUsername(postgres.getUsername());
        config.setPassword(postgres.getPassword());
        config.setDriverClassName("org.postgresql.Driver");
        config.setMaximumPoolSize(2);
        sharedDataSource = new HikariDataSource(config);

        // Load schema.sql to create tables
        var jdbc = new JdbcTemplate(sharedDataSource);
        try (InputStream is = ApiKeyRegistryProjectionTest.class.getClassLoader().getResourceAsStream("schema.sql")) {
            if (is != null) {
                String sql = new String(is.readAllBytes(), StandardCharsets.UTF_8);
                jdbc.execute(sql);
            }
        }
    }

    @BeforeEach
    void setUp() {
        jdbcTemplate = new JdbcTemplate(sharedDataSource);
        jdbcTemplate.update("DELETE FROM api_key_projection");
        registry = new ApiKeyRegistry(jdbcTemplate, new ObjectMapper(),
            new com.realityrag.access.config.AccessProperties(),
            new NoOpApiKeyProjectionCache());
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
            true, 8192, "active", null, 1, Timestamp.from(Instant.now()), true
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
            false, budget, state, expiresAt != null ? Timestamp.from(expiresAt) : null, 1, Timestamp.from(lastUpdated), true
        );
    }

    @Test
    void cachedExpiredRegistrationIsRevalidatedOnResolve() {
        var cache = new InMemoryApiKeyProjectionCache();
        var cachingRegistry = new ApiKeyRegistry(jdbcTemplate, new ObjectMapper(),
            new com.realityrag.access.config.AccessProperties(), cache);

        // Pre-populate the cache with a registration whose expires_at is in the past.
        var expiredReg = new ApiKeyRegistry.AgentRegistration(
            "key-pre-cached-expired", "tnt_default", "kb_assistant",
            List.of(), List.of(), false, 4096, "active",
            Instant.now().minus(1, ChronoUnit.HOURS),
            1, Instant.now()
        );
        cache.set("key-pre-cached-expired", expiredReg);

        // Resolve must re-validate the cached entry and reject it.
        assertThrows(AccessException.Unauthenticated.class,
            () -> cachingRegistry.resolve("key-pre-cached-expired"));
    }

    @Test
    void cachedStaleRegistrationIsRevalidatedOnResolve() {
        var cache = new InMemoryApiKeyProjectionCache();
        var props = new com.realityrag.access.config.AccessProperties();
        props.setStalenessTtlMinutes(60);
        var cachingRegistry = new ApiKeyRegistry(jdbcTemplate, new ObjectMapper(), props, cache);

        var staleReg = new ApiKeyRegistry.AgentRegistration(
            "key-pre-cached-stale", "tnt_default", "kb_assistant",
            List.of(), List.of(), false, 4096, "active",
            null, 1, Instant.now().minus(2, ChronoUnit.HOURS)
        );
        cache.set("key-pre-cached-stale", staleReg);

        assertThrows(AccessException.RegistryUnavailable.class,
            () -> cachingRegistry.resolve("key-pre-cached-stale"));
    }

    private static class InMemoryApiKeyProjectionCache implements ApiKeyProjectionCache {
        private final ConcurrentHashMap<String, ApiKeyRegistry.AgentRegistration> store = new ConcurrentHashMap<>();

        @Override
        public ApiKeyRegistry.AgentRegistration get(String apiKeyId) {
            return store.get(apiKeyId);
        }

        @Override
        public void set(String apiKeyId, ApiKeyRegistry.AgentRegistration registration) {
            store.put(apiKeyId, registration);
        }

        @Override
        public void evict(String apiKeyId) {
            store.remove(apiKeyId);
        }

        public boolean contains(String apiKeyId) {
            return store.containsKey(apiKeyId);
        }

        public boolean isEmpty() {
            return store.isEmpty();
        }
    }
}

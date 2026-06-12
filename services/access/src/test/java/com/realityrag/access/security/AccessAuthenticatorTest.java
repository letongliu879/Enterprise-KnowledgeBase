package com.realityrag.access.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.realityrag.access.support.AccessException;
import com.realityrag.access.support.TestAgentAuthFactory;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.mock.web.MockHttpServletRequest;

@Testcontainers
class AccessAuthenticatorTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    private static ApiKeyRegistry sharedRegistry;

    @BeforeAll
    static void beforeAll() throws Exception {
        sharedRegistry = createApiKeyRegistry();
    }

    private final AccessAuthenticator authenticator = new AccessAuthenticator(sharedRegistry);

    @Test
    void apiKeyAuthenticatesAgentInstance() {
        var request = new MockHttpServletRequest("POST", "/mcp/messages");
        TestAgentAuthFactory.headers("POST", "/mcp/messages", "sessionId=s1")
            .forEach(request::addHeader);
        request.setQueryString("sessionId=s1");

        var context = authenticator.authenticate(request);
        assertEquals("rr-agent-platform-dev", context.apiKeyId());
        assertEquals("tnt_default", context.tenantId());
        assertEquals("kb_assistant", context.agentTypeId());
        assertEquals("agent-instance-001", context.agentInstanceId());
        assertEquals("mcp_message", context.clientType());
        assertEquals(4096, context.maxContextTokens());
    }

    @Test
    void unknownApiKeyFails() {
        var request = new MockHttpServletRequest("GET", "/sse");
        request.addHeader("X-API-Key", "unknown");
        request.addHeader("X-Agent-Instance-Id", "agent-x");

        assertThrows(AccessException.Unauthenticated.class, () -> authenticator.authenticate(request));
    }

    @Test
    void tenantAndPlatformHeadersAreIgnored() {
        var request = new MockHttpServletRequest("POST", "/v1/retrieve");
        request.addHeader("X-API-Key", TestAgentAuthFactory.API_KEY);
        request.addHeader("X-Agent-Instance-Id", "agent-instance-override");
        request.addHeader("X-Tenant-Id", "tenant-from-client");
        request.addHeader("X-Platform-Id", "platform-from-client");

        var context = authenticator.authenticate(request);
        assertEquals("agent-instance-override", context.agentInstanceId());
        // tenant must come from projection, not client header
        assertEquals("tnt_default", context.tenantId());
    }

    @Test
    void disabledKeyFailsClosed() {
        var request = new MockHttpServletRequest("POST", "/v1/retrieve");
        request.addHeader("X-API-Key", "key-disabled");
        request.addHeader("X-Agent-Instance-Id", "agent-x");

        assertThrows(AccessException.Unauthenticated.class, () -> authenticator.authenticate(request));
    }

    @Test
    void revokedKeyFailsClosed() {
        var request = new MockHttpServletRequest("POST", "/v1/retrieve");
        request.addHeader("X-API-Key", "key-revoked");
        request.addHeader("X-Agent-Instance-Id", "agent-x");

        assertThrows(AccessException.Unauthenticated.class, () -> authenticator.authenticate(request));
    }

    @Test
    void expiredKeyFailsClosed() {
        var request = new MockHttpServletRequest("POST", "/v1/retrieve");
        request.addHeader("X-API-Key", "key-expired");
        request.addHeader("X-Agent-Instance-Id", "agent-x");

        assertThrows(AccessException.Unauthenticated.class, () -> authenticator.authenticate(request));
    }

    @Test
    void tokenBudgetLimitIsConsumed() {
        var request = new MockHttpServletRequest("POST", "/v1/retrieve");
        request.addHeader("X-API-Key", "key-low-budget");
        request.addHeader("X-Agent-Instance-Id", "agent-x");

        var context = authenticator.authenticate(request);
        assertEquals(2048, context.maxContextTokens());
    }

    private static ApiKeyRegistry createApiKeyRegistry() throws Exception {
        var config = new HikariConfig();
        config.setJdbcUrl(postgres.getJdbcUrl());
        config.setUsername(postgres.getUsername());
        config.setPassword(postgres.getPassword());
        config.setDriverClassName("org.postgresql.Driver");
        config.setMaximumPoolSize(2);
        var dataSource = new HikariDataSource(config);

        var jdbcTemplate = new JdbcTemplate(dataSource);

        // Load schema.sql to create tables
        try (InputStream is = AccessAuthenticatorTest.class.getClassLoader().getResourceAsStream("schema.sql")) {
            if (is != null) {
                String sql = new String(is.readAllBytes(), StandardCharsets.UTF_8);
                jdbcTemplate.execute(sql);
            }
        }

        jdbcTemplate.update("DELETE FROM api_key_projection");

        Instant now = Instant.now();
        Timestamp nowTs = Timestamp.from(now);
        Timestamp yesterdayTs = Timestamp.from(now.minus(1, ChronoUnit.DAYS));
        // Active key
        jdbcTemplate.update(
            """
                INSERT INTO api_key_projection (
                    api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                    debug_permission, token_budget_limit, state, expires_at,
                    projection_version, last_updated_at, runtime_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            TestAgentAuthFactory.API_KEY,
            "tnt_default",
            "kb_assistant",
            "[\"col_policy\",\"col_handbook\"]",
            "[\"agent\"]",
            false,
            4096,
            "active",
            null,
            1,
            nowTs,
            true
        );
        // Disabled key
        jdbcTemplate.update(
            """
                INSERT INTO api_key_projection (
                    api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                    debug_permission, token_budget_limit, state, expires_at,
                    projection_version, last_updated_at, runtime_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            "key-disabled", "tnt_default", "kb_assistant", "[]", "[]",
            false, 4096, "disabled", null, 1, nowTs, true
        );
        // Revoked key
        jdbcTemplate.update(
            """
                INSERT INTO api_key_projection (
                    api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                    debug_permission, token_budget_limit, state, expires_at,
                    projection_version, last_updated_at, runtime_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            "key-revoked", "tnt_default", "kb_assistant", "[]", "[]",
            false, 4096, "revoked", null, 1, nowTs, true
        );
        // Expired key
        jdbcTemplate.update(
            """
                INSERT INTO api_key_projection (
                    api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                    debug_permission, token_budget_limit, state, expires_at,
                    projection_version, last_updated_at, runtime_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            "key-expired", "tnt_default", "kb_assistant", "[]", "[]",
            false, 4096, "active", yesterdayTs, 1, nowTs, true
        );
        // Low budget key
        jdbcTemplate.update(
            """
                INSERT INTO api_key_projection (
                    api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                    debug_permission, token_budget_limit, state, expires_at,
                    projection_version, last_updated_at, runtime_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            "key-low-budget", "tnt_default", "kb_assistant", "[]", "[]",
            false, 2048, "active", null, 1, nowTs, true
        );

        return new ApiKeyRegistry(jdbcTemplate, new ObjectMapper(),
            new com.realityrag.access.config.AccessProperties(),
            new NoOpApiKeyProjectionCache());
    }
}

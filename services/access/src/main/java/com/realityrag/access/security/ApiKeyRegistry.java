package com.realityrag.access.security;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.config.AccessProperties;
import com.realityrag.access.support.AccessException;
import java.sql.ResultSet;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class ApiKeyRegistry {
    private static final TypeReference<List<String>> STRING_LIST = new TypeReference<>() {};

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;
    private final AccessProperties accessProperties;
    private final ApiKeyProjectionCache cache;

    public ApiKeyRegistry(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper, AccessProperties accessProperties, ApiKeyProjectionCache cache) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.accessProperties = accessProperties;
        this.cache = cache;
    }

    public AgentRegistration resolve(String apiKey) {
        AgentRegistration cached = cache.get(apiKey);
        if (cached != null) {
            try {
                validateRegistration(cached, apiKey);
                return cached;
            } catch (AccessException error) {
                cache.evict(apiKey);
                throw error;
            }
        }
        try {
            List<AgentRegistration> rows = jdbcTemplate.query(
                """
                    SELECT api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                           debug_permission, token_budget_limit, state, expires_at,
                           projection_version, last_updated_at
                    FROM api_key_projection
                    WHERE api_key_id = ?
                    """,
                (rs, rowNum) -> mapRow(rs),
                apiKey
            );
            if (rows.isEmpty()) {
                return null;
            }
            AgentRegistration registration = rows.get(0);
            validateRegistration(registration, apiKey);
            cache.set(apiKey, registration);
            return registration;
        }
        catch (DataAccessException | IllegalStateException error) {
            throw new AccessException.RegistryUnavailable("API key registry lookup failed", error);
        }
    }

    public void invalidateCache(String apiKeyId) {
        cache.evict(apiKeyId);
    }

    private void validateRegistration(AgentRegistration registration, String apiKey) {
        String state = registration.state();
        if (!"active".equals(state)) {
            throw new AccessException.Unauthenticated(
                "API key is " + state + ": " + apiKey
            );
        }

        if (registration.expiresAt() != null
            && registration.expiresAt().isBefore(Instant.now())) {
            throw new AccessException.Unauthenticated(
                "API key has expired: " + apiKey
            );
        }

        int stalenessMinutes = accessProperties.getStalenessTtlMinutes();
        if (stalenessMinutes > 0 && registration.lastUpdatedAt() != null) {
            Instant staleThreshold = Instant.now().minus(stalenessMinutes, ChronoUnit.MINUTES);
            if (registration.lastUpdatedAt().isBefore(staleThreshold)) {
                throw new AccessException.RegistryUnavailable(
                    "API key projection is stale for: " + apiKey
                );
            }
        }
    }

    private AgentRegistration mapRow(ResultSet rs) throws java.sql.SQLException {
        return new AgentRegistration(
            rs.getString("api_key_id"),
            rs.getString("tenant_id"),
            rs.getString("agent_type_id"),
            parseList(rs.getString("knowledge_scopes")),
            parseList(rs.getString("roles")),
            rs.getBoolean("debug_permission"),
            rs.getInt("token_budget_limit"),
            rs.getString("state"),
            rs.getTimestamp("expires_at") == null ? null : rs.getTimestamp("expires_at").toInstant(),
            rs.getInt("projection_version"),
            rs.getTimestamp("last_updated_at") == null ? null : rs.getTimestamp("last_updated_at").toInstant()
        );
    }

    private List<String> parseList(String rawJson) {
        if (rawJson == null || rawJson.isBlank()) {
            return List.of();
        }
        try {
            return List.copyOf(objectMapper.readValue(rawJson, STRING_LIST));
        }
        catch (Exception error) {
            throw new IllegalStateException("Failed to parse api_key_projection JSON column", error);
        }
    }

    public record AgentRegistration(
        String apiKeyId,
        String tenantId,
        String agentTypeId,
        List<String> knowledgeScopes,
        List<String> roles,
        boolean debugPermission,
        int maxContextTokens,
        String state,
        Instant expiresAt,
        int projectionVersion,
        Instant lastUpdatedAt
    ) {}
}

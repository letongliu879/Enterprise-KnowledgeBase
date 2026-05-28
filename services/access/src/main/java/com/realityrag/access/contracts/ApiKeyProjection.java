package com.realityrag.access.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.time.Instant;
import java.util.List;

/**
 * Access runtime projection of an API key.
 *
 * <p>Derived from admin control plane. Uses canonical wire fields.
 * Does NOT include key_hash — access runtime never stores plaintext keys.
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ApiKeyProjection(
    String apiKeyId,
    String tenantId,
    String agentTypeId,
    List<String> knowledgeScopes,
    List<String> roles,
    boolean debugPermission,
    int tokenBudgetLimit,
    String state,
    Instant expiresAt,
    int projectionVersion,
    Instant lastUpdatedAt
) {
    public ApiKeyProjection {
        apiKeyId = apiKeyId == null || apiKeyId.isBlank() ? "" : apiKeyId;
        tenantId = tenantId == null || tenantId.isBlank() ? "" : tenantId;
        agentTypeId = agentTypeId == null || agentTypeId.isBlank() ? "" : agentTypeId;
        knowledgeScopes = knowledgeScopes == null ? List.of() : List.copyOf(knowledgeScopes);
        roles = roles == null ? List.of() : List.copyOf(roles);
        tokenBudgetLimit = tokenBudgetLimit <= 0 ? 4096 : tokenBudgetLimit;
        state = state == null || state.isBlank() ? "active" : state;
        projectionVersion = projectionVersion <= 0 ? 1 : projectionVersion;
    }
}

package com.realityrag.access.security;

import java.util.List;
import java.util.Map;

public record AccessRequestContext(
    String apiKeyId,
    String agentTypeId,
    String agentInstanceId,
    List<String> knowledgeScopes,
    List<String> roles,
    Map<String, Object> attributes,
    boolean debugPermission,
    String clientType,
    int maxContextTokens
) {
    public AccessRequestContext {
        apiKeyId = apiKeyId == null || apiKeyId.isBlank() ? "unknown" : apiKeyId;
        agentTypeId = agentTypeId == null || agentTypeId.isBlank() ? "unknown" : agentTypeId;
        agentInstanceId = agentInstanceId == null || agentInstanceId.isBlank() ? "unknown" : agentInstanceId;
        knowledgeScopes = knowledgeScopes == null ? List.of() : List.copyOf(knowledgeScopes);
        roles = roles == null ? List.of() : List.copyOf(roles);
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
        clientType = clientType == null || clientType.isBlank() ? "rest" : clientType;
        maxContextTokens = maxContextTokens <= 0 ? 4096 : maxContextTokens;
    }
}

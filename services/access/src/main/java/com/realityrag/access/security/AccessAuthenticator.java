package com.realityrag.access.security;

import com.realityrag.access.support.AccessException;
import jakarta.servlet.http.HttpServletRequest;
import java.util.LinkedHashMap;
import org.springframework.stereotype.Component;

@Component
public class AccessAuthenticator {
    private final ApiKeyRegistry apiKeyRegistry;

    public AccessAuthenticator(ApiKeyRegistry apiKeyRegistry) {
        this.apiKeyRegistry = apiKeyRegistry;
    }

    public AccessRequestContext authenticate(HttpServletRequest request) {
        String apiKey = requiredHeader(request, "X-API-Key");
        String agentInstanceId = requiredHeader(request, "X-Agent-Instance-Id");
        var registration = apiKeyRegistry.resolve(apiKey);
        if (registration == null) {
            throw new AccessException.Unauthenticated("Unknown API key");
        }

        LinkedHashMap<String, Object> attributes = new LinkedHashMap<>();
        attributes.put("api_key_id", registration.apiKeyId());
        attributes.put("tenant_id", registration.tenantId());
        attributes.put("agent_type_id", registration.agentTypeId());
        attributes.put("agent_instance_id", agentInstanceId);
        attributes.put("projection_version", registration.projectionVersion());

        return new AccessRequestContext(
            registration.apiKeyId(),
            registration.tenantId(),
            registration.agentTypeId(),
            agentInstanceId,
            registration.knowledgeScopes(),
            registration.roles(),
            attributes,
            registration.debugPermission(),
            resolveClientType(request),
            registration.maxContextTokens()
        );
    }

    private String resolveClientType(HttpServletRequest request) {
        String path = request.getRequestURI();
        if (path != null && path.startsWith("/mcp")) {
            return "mcp_message";
        }
        return "rest";
    }

    private String requiredHeader(HttpServletRequest request, String name) {
        String value = optionalHeader(request, name);
        if (value == null) {
            throw new AccessException.Unauthenticated("Missing header: " + name);
        }
        return value;
    }

    private String optionalHeader(HttpServletRequest request, String name) {
        String value = request.getHeader(name);
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }
}

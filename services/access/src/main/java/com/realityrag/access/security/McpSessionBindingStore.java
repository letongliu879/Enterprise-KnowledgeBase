package com.realityrag.access.security;

import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;

@Component
public class McpSessionBindingStore {
    private final ConcurrentHashMap<String, AccessRequestContext> bindings = new ConcurrentHashMap<>();

    public void bind(String sessionId, AccessRequestContext context) {
        bindings.putIfAbsent(sessionId, context);
    }

    public AccessRequestContext get(String sessionId) {
        return bindings.get(sessionId);
    }

    public boolean matches(String sessionId, AccessRequestContext context) {
        AccessRequestContext bound = bindings.get(sessionId);
        if (bound == null) {
            return true; // First request for this session, will be bound below
        }
        return samePrincipal(bound, context);
    }

    public void remove(String sessionId) {
        bindings.remove(sessionId);
    }

    private boolean samePrincipal(AccessRequestContext left, AccessRequestContext right) {
        return Objects.equals(left.apiKeyId(), right.apiKeyId())
            && Objects.equals(left.agentTypeId(), right.agentTypeId())
            && Objects.equals(left.agentInstanceId(), right.agentInstanceId())
            && Objects.equals(left.knowledgeScopes(), right.knowledgeScopes());
    }
}

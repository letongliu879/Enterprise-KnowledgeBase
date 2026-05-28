package com.realityrag.access.security;

import com.realityrag.access.support.AccessException;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;

@Component
public class McpSessionPrincipalBindingStore {
    private final ConcurrentHashMap<String, AccessRequestContext> bindings = new ConcurrentHashMap<>();

    public void bind(String sessionId, AccessRequestContext context) {
        bindings.put(sessionId, context);
    }

    public AccessRequestContext get(String sessionId) {
        return bindings.get(sessionId);
    }

    public void assertMatches(String sessionId, AccessRequestContext context) {
        AccessRequestContext bound = bindings.get(sessionId);
        if (bound == null) {
            return;
        }
        if (!samePrincipal(bound, context)) {
            throw new AccessException.Forbidden(
                "MCP session principal does not match the authenticated bearer token"
            );
        }
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

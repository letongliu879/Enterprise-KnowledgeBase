package com.realityrag.access.mcp;

import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.security.AccessRequestContext;
import com.realityrag.access.support.AccessException;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class McpKnowledgeScopeMapper {
    public ExternalRetrieveRequest map(
        String query,
        String knowledgeScope,
        String retrievalProfileId,
        Integer tokenBudget,
        String debug,
        AccessRequestContext context
    ) {
        String scope = knowledgeScope.trim();
        if (!context.knowledgeScopes().contains(scope)) {
            throw new AccessException.Forbidden("Knowledge scope is not allowed for this agent integration");
        }
        return new ExternalRetrieveRequest(
            query,
            List.of(scope),
            java.util.Map.of(),
            null,
            List.of(),
            false,
            java.util.Map.of(),
            retrievalProfileId,
            null,
            tokenBudget,
            debug
        );
    }
}

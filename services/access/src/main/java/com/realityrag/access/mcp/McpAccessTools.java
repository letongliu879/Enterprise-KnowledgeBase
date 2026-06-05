package com.realityrag.access.mcp;

import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.security.AccessRequestContext;
import com.realityrag.access.security.AccessRequestContextHolder;
import com.realityrag.access.service.AccessGatewayService;
import com.realityrag.access.support.AccessException;
import java.util.List;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

@Component
public class McpAccessTools {
    private final AccessGatewayService accessGatewayService;

    public McpAccessTools(AccessGatewayService accessGatewayService) {
        this.accessGatewayService = accessGatewayService;
    }

    @Tool(
        name = "search_enterprise_knowledge",
        description = "Use only when you need enterprise-internal knowledge or policy context. Do not use for public facts, casual chat, code generation, or questions already answerable from the current conversation."
    )
    public KnowledgeContext retrieveKnowledgeContext(
        @ToolParam(description = "User question to search in enterprise knowledge.", required = true) String query,
        @ToolParam(description = "Allowed knowledge scope / collection id to search.", required = true) String knowledge_scope,
        @ToolParam(description = "Optional retrieval profile id.") String retrieval_profile_id,
        @ToolParam(description = "Optional token budget.") Integer token_budget,
        @ToolParam(description = "Debug level: none, basic, or full.") String debug,
        ToolContext toolContext
    ) {
        AccessRequestContext context = resolveContext(toolContext);
        return accessGatewayService.retrieveWithContext(
            buildRequest(query, knowledge_scope, retrieval_profile_id, token_budget, debug, context),
            context
        );
    }

    private AccessRequestContext resolveContext(ToolContext toolContext) {
        AccessRequestContext context = AccessRequestContextHolder.get();
        if (context == null) {
            throw new AccessException.Unauthenticated("Missing MCP access context");
        }
        return context;
    }

    private ExternalRetrieveRequest buildRequest(
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

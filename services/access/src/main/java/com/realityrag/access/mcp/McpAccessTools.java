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
        @ToolParam(description = "Knowledge scope / collection id to search. If omitted, all authorized scopes are searched.", required = false) String knowledge_scope,
        @ToolParam(description = "Optional token budget.") Integer token_budget,
        @ToolParam(description = "Debug level: none, basic, or full.") String debug,
        ToolContext toolContext
    ) {
        AccessRequestContext context = resolveContext(toolContext);
        return accessGatewayService.retrieveWithContext(
            buildRequest(query, knowledge_scope, token_budget, debug, context),
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
        Integer tokenBudget,
        String debug,
        AccessRequestContext context
    ) {
        List<String> scopes;
        if (knowledgeScope == null || knowledgeScope.isBlank()) {
            scopes = context.knowledgeScopes();
        } else {
            String scope = knowledgeScope.trim();
            if (!context.knowledgeScopes().contains(scope)) {
                throw new AccessException.Forbidden(
                    "Knowledge scope '" + scope + "' is not allowed. Allowed scopes: " + context.knowledgeScopes()
                );
            }
            scopes = List.of(scope);
        }
        return new ExternalRetrieveRequest(
            query,
            scopes,
            java.util.Map.of(),
            null,
            List.of(),
            false,
            java.util.Map.of(),
            null,
            null,
            tokenBudget,
            debug
        );
    }
}

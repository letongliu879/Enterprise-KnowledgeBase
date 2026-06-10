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
        description = """
            检索企业内部知识库。用于查询所有项目特定的、团队内部的、非公开通用的信息。

            必须使用的情况：
            - 用户问题涉及"我们团队/公司/项目是如何做的"
            - 需要确认企业内部规范、约定、流程、架构决策
            - 任何你不确定是否属于企业内部特定上下文的问题

            不使用的情况：
            - 公开的技术事实、通用编程问题
            - 已能从当前对话中直接回答的问题
            - 纯闲聊或代码生成任务
            """
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

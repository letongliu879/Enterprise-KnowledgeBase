package com.realityrag.access.mcp;

import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.security.AccessRequestContext;
import com.realityrag.access.security.AccessRequestContextHolder;
import com.realityrag.access.security.McpSessionPrincipalBindingStore;
import com.realityrag.access.service.AccessGatewayService;
import com.realityrag.access.support.AccessException;
import io.modelcontextprotocol.spec.McpServerSession;
import java.lang.reflect.Field;
import java.util.Optional;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.mcp.McpToolUtils;
import org.springframework.ai.tool.annotation.ToolParam;
import io.modelcontextprotocol.server.McpSyncServerExchange;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

@Component
public class McpAccessTools {
    private final AccessGatewayService accessGatewayService;
    private final McpKnowledgeScopeMapper knowledgeScopeMapper;
    private final McpSessionPrincipalBindingStore sessionBindingStore;

    public McpAccessTools(
        AccessGatewayService accessGatewayService,
        McpKnowledgeScopeMapper knowledgeScopeMapper,
        McpSessionPrincipalBindingStore sessionBindingStore
    ) {
        this.accessGatewayService = accessGatewayService;
        this.knowledgeScopeMapper = knowledgeScopeMapper;
        this.sessionBindingStore = sessionBindingStore;
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
        if (context == null) {
            throw new AccessException.Unauthenticated("Missing MCP access context");
        }
        return accessGatewayService.retrieveWithContext(
            knowledgeScopeMapper.map(query, knowledge_scope, retrieval_profile_id, token_budget, debug, context),
            context
        );
    }

    private AccessRequestContext resolveContext(ToolContext toolContext) {
        String sessionId = extractSessionId(toolContext).orElse(null);
        if (sessionId != null) {
            AccessRequestContext boundContext = sessionBindingStore.get(sessionId);
            if (boundContext != null) {
                return boundContext;
            }
        }
        return AccessRequestContextHolder.get();
    }

    private Optional<String> extractSessionId(ToolContext toolContext) {
        return McpToolUtils.getMcpExchange(toolContext)
            .map(this::extractAsyncExchange)
            .map(this::extractSession)
            .map(McpServerSession::getId);
    }

    private Object extractAsyncExchange(McpSyncServerExchange syncExchange) {
        try {
            Field field = McpSyncServerExchange.class.getDeclaredField("exchange");
            field.setAccessible(true);
            return field.get(syncExchange);
        }
        catch (ReflectiveOperationException error) {
            throw new IllegalStateException("Unable to extract MCP async exchange from tool context", error);
        }
    }

    private McpServerSession extractSession(Object asyncExchange) {
        try {
            Field field = asyncExchange.getClass().getDeclaredField("session");
            field.setAccessible(true);
            Object value = field.get(asyncExchange);
            if (value instanceof McpServerSession session) {
                return session;
            }
        }
        catch (ReflectiveOperationException error) {
            throw new IllegalStateException("Unable to extract MCP session from tool context", error);
        }
        throw new IllegalStateException("MCP tool context session is missing");
    }
}

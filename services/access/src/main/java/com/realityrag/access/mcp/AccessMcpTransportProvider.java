package com.realityrag.access.mcp;

import com.realityrag.access.security.AccessRequestContext;
import com.realityrag.access.security.AccessRequestContextHolder;
import com.realityrag.access.security.McpSessionPrincipalBindingStore;
import com.realityrag.access.support.AccessUnauthenticatedException;
import io.modelcontextprotocol.server.transport.WebMvcSseServerTransportProvider;
import io.modelcontextprotocol.spec.McpServerSession;
import io.modelcontextprotocol.spec.McpServerTransport;
import io.modelcontextprotocol.spec.McpServerTransportProvider;
import java.lang.reflect.Field;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Mono;
import org.springframework.web.servlet.function.RouterFunction;
import org.springframework.web.servlet.function.ServerResponse;

public class AccessMcpTransportProvider implements McpServerTransportProvider {
    private static final Logger log = LoggerFactory.getLogger(AccessMcpTransportProvider.class);
    private final WebMvcSseServerTransportProvider delegate;
    private final McpSessionPrincipalBindingStore bindingStore;

    public AccessMcpTransportProvider(
        WebMvcSseServerTransportProvider delegate,
        McpSessionPrincipalBindingStore bindingStore
    ) {
        this.delegate = delegate;
        this.bindingStore = bindingStore;
    }

    @Override
    public void setSessionFactory(McpServerSession.Factory sessionFactory) {
        delegate.setSessionFactory(transport -> {
            AccessRequestContext context = AccessRequestContextHolder.get();
            if (context == null) {
                log.warn("ACCESS_MCP event=session_bind_missing_context");
                throw new AccessUnauthenticatedException("Missing MCP session access context");
            }
            String transportSessionId = extractSessionId(transport);
            McpServerSession session = sessionFactory.create(transport);
            log.info(
                "ACCESS_MCP event=session_bind transport_session_id={} server_session_id={} api_key_id={} agent_instance_id={}",
                transportSessionId,
                session.getId(),
                context.apiKeyId(),
                context.agentInstanceId()
            );
            bindingStore.bind(transportSessionId, context);
            bindingStore.bind(session.getId(), context);
            return session;
        });
    }

    @Override
    public Mono<Void> notifyClients(String method, Object params) {
        return delegate.notifyClients(method, params);
    }

    @Override
    public Mono<Void> closeGracefully() {
        return delegate.closeGracefully();
    }

    @Override
    public void close() {
        delegate.close();
    }

    public RouterFunction<ServerResponse> routerFunction() {
        return delegate.getRouterFunction();
    }

    private String extractSessionId(McpServerTransport transport) {
        try {
            Field field = transport.getClass().getDeclaredField("sessionId");
            field.setAccessible(true);
            Object value = field.get(transport);
            if (value instanceof String sessionId && !sessionId.isBlank()) {
                return sessionId;
            }
        }
        catch (ReflectiveOperationException error) {
            throw new IllegalStateException("Unable to extract MCP session id from transport", error);
        }
        throw new IllegalStateException("MCP transport session id is missing");
    }
}

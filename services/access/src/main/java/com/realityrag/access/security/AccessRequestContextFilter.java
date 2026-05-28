package com.realityrag.access.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.contracts.AccessErrorResponse;
import com.realityrag.access.support.AccessException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class AccessRequestContextFilter extends OncePerRequestFilter {
    private static final Logger log = LoggerFactory.getLogger(AccessRequestContextFilter.class);
    private final AccessAuthenticator accessAuthenticator;
    private final McpSessionPrincipalBindingStore sessionBindingStore;
    private final ObjectMapper objectMapper;

    public AccessRequestContextFilter(
        AccessAuthenticator accessAuthenticator,
        McpSessionPrincipalBindingStore sessionBindingStore,
        ObjectMapper objectMapper
    ) {
        this.accessAuthenticator = accessAuthenticator;
        this.sessionBindingStore = sessionBindingStore;
        this.objectMapper = objectMapper;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        if (path == null) {
            return false;
        }
        return path.equals("/health")
            || path.startsWith("/actuator")
            || path.startsWith("/internal");
    }

    @Override
    protected boolean shouldNotFilterAsyncDispatch() {
        return true;
    }

    @Override
    protected boolean shouldNotFilterErrorDispatch() {
        return true;
    }

    @Override
    protected void doFilterInternal(
        HttpServletRequest request,
        HttpServletResponse response,
        FilterChain filterChain
    ) throws ServletException, IOException {
        String path = request.getRequestURI();
        try {
            AccessRequestContext context = accessAuthenticator.authenticate(request);
            if (path != null && path.startsWith("/mcp/messages")) {
                String sessionId = request.getParameter("sessionId");
                if (sessionId != null && !sessionId.isBlank()) {
                    sessionBindingStore.assertMatches(sessionId, context);
                    AccessRequestContext boundContext = sessionBindingStore.get(sessionId);
                    if (boundContext != null) {
                        context = boundContext;
                    }
                }
            }
            AccessRequestContextHolder.set(context);
            if (path != null && path.startsWith("/sse")) {
                request.setAttribute(AccessRequestContext.class.getName(), context);
            }
            filterChain.doFilter(request, response);
        } catch (AccessException error) {
            log.warn(
                "ACCESS_AUDIT event=auth_failure method={} path={} status_code={} error_code={} error_message={} api_key_id={} agent_instance_id={}",
                request.getMethod(),
                request.getRequestURI(),
                error.getStatus().value(),
                error.getErrorCode(),
                error.getMessage(),
                request.getHeader("X-API-Key"),
                request.getHeader("X-Agent-Instance-Id")
            );
            writeError(response, error);
        } finally {
            AccessRequestContextHolder.clear();
        }
    }

    private void writeError(HttpServletResponse response, AccessException error) throws IOException {
        if (response.isCommitted()) {
            return;
        }
        response.resetBuffer();
        response.setStatus(error.getStatus().value());
        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");
        objectMapper.writeValue(response.getWriter(), new AccessErrorResponse(
            error.getErrorCode(),
            error.getMessage()
        ));
        response.flushBuffer();
    }
}

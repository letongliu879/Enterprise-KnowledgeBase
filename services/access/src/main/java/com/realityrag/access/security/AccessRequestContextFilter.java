package com.realityrag.access.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.contracts.AccessErrorResponse;
import com.realityrag.access.support.AccessException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.net.InetAddress;
import java.net.UnknownHostException;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.util.ContentCachingResponseWrapper;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class AccessRequestContextFilter extends OncePerRequestFilter {
    private static final Logger log = LoggerFactory.getLogger(AccessRequestContextFilter.class);
    private static final Set<String> ALLOWED_INTERNAL_ADDRESSES = Set.of("127.0.0.1", "0:0:0:0:0:0:0:1", "localhost");
    private final AccessAuthenticator accessAuthenticator;
    private final McpSessionBindingStore sessionBindingStore;
    private final ObjectMapper objectMapper;

    public AccessRequestContextFilter(
        AccessAuthenticator accessAuthenticator,
        McpSessionBindingStore sessionBindingStore,
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
        // Internal endpoints are routed through doFilterInternal for IP whitelist check
        return path.equals("/health") || path.startsWith("/actuator");
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
        if (path != null && path.startsWith("/internal")) {
            if (!isAllowedInternalAddress(request.getRemoteAddr())) {
                log.warn("Blocked internal endpoint access from {}", request.getRemoteAddr());
                response.setStatus(HttpServletResponse.SC_FORBIDDEN);
                return;
            }
            filterChain.doFilter(request, response);
            return;
        }

        boolean isMcpStream = path != null && path.equals("/mcp");
        if (isMcpStream) {
            try {
                AccessRequestContext context = accessAuthenticator.authenticate(request);
                String mcpSessionId = request.getHeader("Mcp-Session-Id");
                if (mcpSessionId != null && !mcpSessionId.isBlank()) {
                    if (!sessionBindingStore.matches(mcpSessionId, context)) {
                        writeError(response, new AccessException.Forbidden(
                            "MCP session principal does not match the authenticated identity"
                        ));
                        return;
                    }
                }
                AccessRequestContextHolder.set(context);
                filterChain.doFilter(request, response);
                String responseSessionId = response.getHeader("Mcp-Session-Id");
                if (responseSessionId != null) {
                    sessionBindingStore.bind(responseSessionId, context);
                }
            } catch (AccessException error) {
                log.warn(
                    "ACCESS_AUDIT event=auth_failure method={} path={} status_code={} error_code={} error_message={} api_key_id={} agent_instance_id={}",
                    request.getMethod(), request.getRequestURI(),
                    error.getStatus().value(), error.getErrorCode(), error.getMessage(),
                    request.getHeader("X-API-Key"), request.getHeader("X-Agent-Instance-Id")
                );
                writeError(response, error);
            } finally {
                AccessRequestContextHolder.clear();
            }
            return;
        }

        ContentCachingResponseWrapper wrappedResponse = new ContentCachingResponseWrapper(response);
        try {
            AccessRequestContext context = accessAuthenticator.authenticate(request);

            // Streamable HTTP session principal drift detection:
            // If client sends an existing session id but with a different principal,
            // reject the request to prevent session hijacking.
            String mcpSessionId = request.getHeader("Mcp-Session-Id");
            if (mcpSessionId != null && !mcpSessionId.isBlank()) {
                if (!sessionBindingStore.matches(mcpSessionId, context)) {
                    throw new AccessException.Forbidden(
                        "MCP session principal does not match the authenticated identity"
                    );
                }
            }

            AccessRequestContextHolder.set(context);
            filterChain.doFilter(request, wrappedResponse);

            // Bind server-allocated sessionId to the authenticated principal
            // so that subsequent requests with a different principal are rejected.
            String responseSessionId = wrappedResponse.getHeader("Mcp-Session-Id");
            if (responseSessionId != null) {
                sessionBindingStore.bind(responseSessionId, context);
            }

            wrappedResponse.copyBodyToResponse();
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

    private boolean isAllowedInternalAddress(String remoteAddr) {
        if (ALLOWED_INTERNAL_ADDRESSES.contains(remoteAddr)) {
            return true;
        }
        try {
            InetAddress addr = InetAddress.getByName(remoteAddr);
            // Allow loopback and RFC1918 private addresses so containerized
            // smoke tests and inter-service calls on Docker networks succeed.
            return addr.isLoopbackAddress() || addr.isSiteLocalAddress();
        } catch (UnknownHostException e) {
            return false;
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

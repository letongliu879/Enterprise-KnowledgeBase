package com.realityrag.access.security;

import jakarta.annotation.PreDestroy;
import java.time.Duration;
import java.time.Instant;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import org.springframework.stereotype.Component;

@Component
public class McpSessionBindingStore {
    private static final Duration SESSION_TTL = Duration.ofHours(24);

    private final ConcurrentHashMap<String, BindingEntry> bindings = new ConcurrentHashMap<>();
    private final ScheduledExecutorService cleanupExecutor = Executors.newSingleThreadScheduledExecutor(
        r -> {
            Thread t = new Thread(r, "mcp-session-cleanup");
            t.setDaemon(true);
            return t;
        }
    );

    public McpSessionBindingStore() {
        cleanupExecutor.scheduleAtFixedRate(this::evictExpired, 1, 1, TimeUnit.MINUTES);
    }

    public void bind(String sessionId, AccessRequestContext context) {
        bindings.putIfAbsent(sessionId, new BindingEntry(context, Instant.now()));
    }

    public AccessRequestContext get(String sessionId) {
        BindingEntry entry = bindings.get(sessionId);
        if (entry == null) {
            return null;
        }
        if (isExpired(entry)) {
            bindings.remove(sessionId);
            return null;
        }
        return entry.context();
    }

    public boolean matches(String sessionId, AccessRequestContext context) {
        BindingEntry entry = bindings.get(sessionId);
        if (entry == null) {
            return true; // First request for this session, will be bound below
        }
        if (isExpired(entry)) {
            bindings.remove(sessionId);
            return true; // Expired, treat as first request
        }
        return samePrincipal(entry.context(), context);
    }

    public void remove(String sessionId) {
        bindings.remove(sessionId);
    }

    @PreDestroy
    public void shutdown() {
        cleanupExecutor.shutdown();
        try {
            if (!cleanupExecutor.awaitTermination(5, TimeUnit.SECONDS)) {
                cleanupExecutor.shutdownNow();
            }
        } catch (InterruptedException e) {
            cleanupExecutor.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }

    private void evictExpired() {
        Instant cutoff = Instant.now().minus(SESSION_TTL);
        bindings.entrySet().removeIf(entry -> entry.getValue().boundAt().isBefore(cutoff));
    }

    private boolean isExpired(BindingEntry entry) {
        return entry.boundAt().plus(SESSION_TTL).isBefore(Instant.now());
    }

    private boolean samePrincipal(AccessRequestContext left, AccessRequestContext right) {
        return Objects.equals(left.apiKeyId(), right.apiKeyId())
            && Objects.equals(left.agentTypeId(), right.agentTypeId())
            && Objects.equals(left.agentInstanceId(), right.agentInstanceId())
            && Objects.equals(left.knowledgeScopes(), right.knowledgeScopes());
    }

    private record BindingEntry(AccessRequestContext context, Instant boundAt) {}
}

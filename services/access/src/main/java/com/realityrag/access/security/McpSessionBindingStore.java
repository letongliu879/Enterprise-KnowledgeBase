package com.realityrag.access.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.config.AccessProperties;
import io.lettuce.core.RedisURI;
import jakarta.annotation.PreDestroy;
import java.time.Duration;
import java.time.Instant;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.connection.RedisStandaloneConfiguration;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
public class McpSessionBindingStore {
    private static final Logger log = LoggerFactory.getLogger(McpSessionBindingStore.class);

    private final AccessProperties properties;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate redisTemplate;
    private final Duration sessionTtl;
    private final ConcurrentHashMap<String, BindingEntry> bindings = new ConcurrentHashMap<>();
    private final ScheduledExecutorService cleanupExecutor = Executors.newSingleThreadScheduledExecutor(
        r -> { Thread t = new Thread(r, "mcp-session-cleanup"); t.setDaemon(true); return t; }
    );

    public McpSessionBindingStore(AccessProperties properties, ObjectMapper objectMapper) {
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.sessionTtl = Duration.ofHours(properties.getMcpSessionTtlHours());
        this.redisTemplate = createRedisTemplate();
        if (!"redis".equals(properties.getCache().getProvider())) {
            cleanupExecutor.scheduleAtFixedRate(this::evictExpired, 1, 1, TimeUnit.MINUTES);
        }
    }

    private StringRedisTemplate createRedisTemplate() {
        String redisUrl = properties.getCache().getRedisUrl();
        try {
            RedisURI uri = RedisURI.create(redisUrl);
            RedisStandaloneConfiguration config = new RedisStandaloneConfiguration();
            config.setHostName(uri.getHost());
            config.setPort(uri.getPort());
            if (uri.getDatabase() >= 0) config.setDatabase(uri.getDatabase());
            if (uri.getPassword() != null) config.setPassword(String.valueOf(uri.getPassword()));
            LettuceConnectionFactory factory = new LettuceConnectionFactory(config);
            factory.afterPropertiesSet();
            StringRedisTemplate template = new StringRedisTemplate(factory);
            template.afterPropertiesSet();
            return template;
        } catch (Exception error) {
            log.warn("Redis not available for MCP session store, falling back to local: {}", error.getMessage());
            return null;
        }
    }

    public void bind(String sessionId, AccessRequestContext context) {
        String key = sessionKey(sessionId);
        if (redisTemplate != null) {
            try {
                redisTemplate.opsForValue().set(key, objectMapper.writeValueAsString(context), sessionTtl);
                return;
            } catch (Exception error) {
                log.warn("Redis session bind failed, falling back to local for session={}: {}", sessionId, error.getMessage());
            }
        }
        bindings.putIfAbsent(sessionId, new BindingEntry(context, Instant.now()));
    }

    public boolean matches(String sessionId, AccessRequestContext context) {
        if (redisTemplate != null) {
            try {
                String value = redisTemplate.opsForValue().get(sessionKey(sessionId));
                if (value == null) return true;
                AccessRequestContext stored = objectMapper.readValue(value, AccessRequestContext.class);
                return samePrincipal(stored, context);
            } catch (Exception error) {
                log.warn("Redis session read failed, checking local for session={}: {}", sessionId, error.getMessage());
            }
        }
        return localMatches(sessionId, context);
    }

    public void remove(String sessionId) {
        if (redisTemplate != null) {
            try { redisTemplate.delete(sessionKey(sessionId)); } catch (Exception ignored) {}
        }
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

    private boolean localMatches(String sessionId, AccessRequestContext context) {
        BindingEntry entry = bindings.get(sessionId);
        if (entry == null) return true;
        if (entry.boundAt().plus(sessionTtl).isBefore(Instant.now())) {
            bindings.remove(sessionId);
            return false;
        }
        return samePrincipal(entry.context(), context);
    }

    private void evictExpired() {
        Instant cutoff = Instant.now().minus(sessionTtl);
        bindings.entrySet().removeIf(e -> e.getValue().boundAt().isBefore(cutoff));
    }

    private boolean samePrincipal(AccessRequestContext left, AccessRequestContext right) {
        return Objects.equals(left.apiKeyId(), right.apiKeyId())
            && Objects.equals(left.agentTypeId(), right.agentTypeId())
            && Objects.equals(left.agentInstanceId(), right.agentInstanceId())
            && Objects.equals(left.knowledgeScopes(), right.knowledgeScopes());
    }

    private String sessionKey(String sessionId) {
        return properties.getCache().getKeyPrefix() + ":session:" + sessionId;
    }

    private record BindingEntry(AccessRequestContext context, Instant boundAt) {}
}

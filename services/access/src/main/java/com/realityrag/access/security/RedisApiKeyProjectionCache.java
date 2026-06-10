package com.realityrag.access.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.config.AccessProperties;
import io.lettuce.core.RedisURI;
import java.time.Duration;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.connection.RedisStandaloneConfiguration;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "access.cache.provider", havingValue = "redis")
public class RedisApiKeyProjectionCache implements ApiKeyProjectionCache {
    private static final Logger log = LoggerFactory.getLogger(RedisApiKeyProjectionCache.class);

    private final AccessProperties properties;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate redisTemplate;

    public RedisApiKeyProjectionCache(AccessProperties properties, ObjectMapper objectMapper) {
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.redisTemplate = createRedisTemplate(properties.getCache().getRedisUrl());
    }

    private static StringRedisTemplate createRedisTemplate(String redisUrl) {
        RedisURI uri = RedisURI.create(redisUrl);
        RedisStandaloneConfiguration config = new RedisStandaloneConfiguration();
        config.setHostName(uri.getHost());
        config.setPort(uri.getPort());
        if (uri.getDatabase() >= 0) {
            config.setDatabase(uri.getDatabase());
        }
        if (uri.getPassword() != null) {
            config.setPassword(String.valueOf(uri.getPassword()));
        }
        LettuceConnectionFactory factory = new LettuceConnectionFactory(config);
        factory.afterPropertiesSet();
        StringRedisTemplate template = new StringRedisTemplate(factory);
        template.afterPropertiesSet();
        return template;
    }

    @Override
    public ApiKeyRegistry.AgentRegistration get(String apiKeyId) {
        try {
            String key = cacheKey(apiKeyId);
            String value = redisTemplate.opsForValue().get(key);
            if (value == null) {
                return null;
            }
            return objectMapper.readValue(value, ApiKeyRegistry.AgentRegistration.class);
        } catch (Exception error) {
            log.warn("Redis projection cache read failed for key={}: {}", apiKeyId, error.getMessage());
            if (properties.getCache().isFailOpen()) {
                return null;
            }
            throw new IllegalStateException("Redis read failed for key=" + apiKeyId, error);
        }
    }

    @Override
    public void set(String apiKeyId, ApiKeyRegistry.AgentRegistration registration) {
        try {
            String key = cacheKey(apiKeyId);
            String json = objectMapper.writeValueAsString(registration);
            redisTemplate.opsForValue().set(key, json, Duration.ofSeconds(properties.getCache().getProjectionTtlSeconds()));
        } catch (Exception error) {
            log.warn("Redis projection cache write failed for key={}: {}", apiKeyId, error.getMessage());
            if (!properties.getCache().isFailOpen()) {
                throw new IllegalStateException("Redis write failed for key=" + apiKeyId, error);
            }
        }
    }

    @Override
    public void evict(String apiKeyId) {
        try {
            redisTemplate.delete(cacheKey(apiKeyId));
        } catch (Exception error) {
            log.warn("Redis projection cache evict failed for key={}: {}", apiKeyId, error.getMessage());
        }
    }

    private String cacheKey(String apiKeyId) {
        return properties.getCache().getKeyPrefix() + ":projection:" + apiKeyId;
    }
}

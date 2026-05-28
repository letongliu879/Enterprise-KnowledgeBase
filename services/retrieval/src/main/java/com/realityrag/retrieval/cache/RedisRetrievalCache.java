package com.realityrag.retrieval.cache;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.lettuce.core.RedisURI;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.connection.RedisStandaloneConfiguration;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "retrieval.cache.provider", havingValue = "redis")
public class RedisRetrievalCache implements RetrievalCache {
    private static final Logger LOG = LoggerFactory.getLogger(RedisRetrievalCache.class);

    private final RetrievalCacheProperties properties;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate redisTemplate;

    public RedisRetrievalCache(RetrievalCacheProperties properties, ObjectMapper objectMapper) {
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.redisTemplate = createRedisTemplate(properties.getRedisUrl());
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
    public <T> T get(String key, Class<T> type) {
        try {
            String value = redisTemplate.opsForValue().get(key);
            if (value == null) {
                return null;
            }
            return objectMapper.readValue(value, type);
        } catch (Exception error) {
            LOG.warn("Redis cache read failed for key={}, type={}: {}", key, type.getSimpleName(), error.getMessage());
            if (properties.isFailOpen()) {
                return null;
            }
            throw new IllegalStateException("Redis cache read failed for key=" + key, error);
        }
    }

    @Override
    public <T> T get(String key, TypeReference<T> typeReference) {
        try {
            String value = redisTemplate.opsForValue().get(key);
            if (value == null) {
                return null;
            }
            return objectMapper.readValue(value, typeReference);
        } catch (Exception error) {
            LOG.warn("Redis cache read failed for key={}, type={}: {}", key, typeReference, error.getMessage());
            if (properties.isFailOpen()) {
                return null;
            }
            throw new IllegalStateException("Redis cache read failed for key=" + key, error);
        }
    }

    @Override
    public void set(String key, Object value, long ttlSeconds) {
        try {
            String json = objectMapper.writeValueAsString(value);
            redisTemplate.opsForValue().set(key, json, Duration.ofSeconds(ttlSeconds));
        } catch (Exception error) {
            LOG.warn("Redis cache write failed for key={}: {}", key, error.getMessage());
            if (!properties.isFailOpen()) {
                throw new IllegalStateException("Redis cache write failed for key=" + key, error);
            }
        }
    }

    @Override
    public boolean delete(String key) {
        try {
            return Boolean.TRUE.equals(redisTemplate.delete(key));
        } catch (Exception error) {
            LOG.warn("Redis cache delete failed for key={}: {}", key, error.getMessage());
            if (!properties.isFailOpen()) {
                throw new IllegalStateException("Redis cache delete failed for key=" + key, error);
            }
            return false;
        }
    }

    @Override
    public long deleteByPattern(String pattern) {
        try {
            var keys = redisTemplate.keys(pattern);
            if (keys == null || keys.isEmpty()) {
                return 0;
            }
            long deleted = redisTemplate.delete(keys);
            LOG.info("Redis cache purge: pattern={}, deleted={}", pattern, deleted);
            return deleted;
        } catch (Exception error) {
            LOG.warn("Redis cache deleteByPattern failed for pattern={}: {}", pattern, error.getMessage());
            if (!properties.isFailOpen()) {
                throw new IllegalStateException("Redis cache deleteByPattern failed for pattern=" + pattern, error);
            }
            return 0;
        }
    }

    @Override
    public boolean isAvailable() {
        try {
            String pong = redisTemplate.getConnectionFactory().getConnection().ping();
            boolean available = "PONG".equalsIgnoreCase(pong);
            if (!available && properties.isRequireRedis()) {
                throw new IllegalStateException("Redis cache required but ping returned non-PONG response");
            }
            return available;
        } catch (IllegalStateException strictError) {
            throw strictError;
        } catch (Exception error) {
            LOG.warn("Redis cache health check failed: {}", error.getMessage());
            if (properties.isRequireRedis()) {
                throw new IllegalStateException("Redis cache required but unavailable: " + error.getMessage(), error);
            }
            return false;
        }
    }
}

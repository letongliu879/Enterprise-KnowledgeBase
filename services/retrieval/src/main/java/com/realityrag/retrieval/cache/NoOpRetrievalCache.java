package com.realityrag.retrieval.cache;

import com.fasterxml.jackson.core.type.TypeReference;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "retrieval.cache.provider", havingValue = "noop", matchIfMissing = true)
public class NoOpRetrievalCache implements RetrievalCache {
    @Override
    public <T> T get(String key, Class<T> type) {
        return null;
    }

    @Override
    public <T> T get(String key, TypeReference<T> typeReference) {
        return null;
    }

    @Override
    public void set(String key, Object value, long ttlSeconds) {
        // no-op
    }

    @Override
    public boolean delete(String key) {
        return false;
    }

    @Override
    public long deleteByPattern(String pattern) {
        return 0;
    }

    @Override
    public boolean isAvailable() {
        return false;
    }
}

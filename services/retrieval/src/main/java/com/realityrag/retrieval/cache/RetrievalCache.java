package com.realityrag.retrieval.cache;

import com.fasterxml.jackson.core.type.TypeReference;

public interface RetrievalCache {
    <T> T get(String key, Class<T> type);

    <T> T get(String key, TypeReference<T> typeReference);

    void set(String key, Object value, long ttlSeconds);

    boolean delete(String key);

    long deleteByPattern(String pattern);

    boolean isAvailable();
}

package com.realityrag.retrieval.cache;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "retrieval.cache")
public class RetrievalCacheProperties {
    private boolean enabled = true;
    private String provider = "noop";
    private String redisUrl = "redis://127.0.0.1:6379/0";
    private String keyPrefix = "reality-rag:retrieval";
    private long queryEmbeddingTtlSeconds = 86400;
    private long recallTtlSeconds = 60;
    private boolean failOpen = true;
    private boolean requireRedis = false;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getProvider() {
        return provider;
    }

    public void setProvider(String provider) {
        this.provider = provider;
    }

    public String getRedisUrl() {
        return redisUrl;
    }

    public void setRedisUrl(String redisUrl) {
        this.redisUrl = redisUrl;
    }

    public String getKeyPrefix() {
        return keyPrefix;
    }

    public void setKeyPrefix(String keyPrefix) {
        this.keyPrefix = keyPrefix;
    }

    public long getQueryEmbeddingTtlSeconds() {
        return queryEmbeddingTtlSeconds;
    }

    public void setQueryEmbeddingTtlSeconds(long queryEmbeddingTtlSeconds) {
        this.queryEmbeddingTtlSeconds = queryEmbeddingTtlSeconds;
    }

    public long getRecallTtlSeconds() {
        return recallTtlSeconds;
    }

    public void setRecallTtlSeconds(long recallTtlSeconds) {
        this.recallTtlSeconds = recallTtlSeconds;
    }

    public boolean isFailOpen() {
        return failOpen;
    }

    public void setFailOpen(boolean failOpen) {
        this.failOpen = failOpen;
    }

    public boolean isRequireRedis() {
        return requireRedis;
    }

    public void setRequireRedis(boolean requireRedis) {
        this.requireRedis = requireRedis;
    }
}

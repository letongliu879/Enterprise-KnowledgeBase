package com.realityrag.access.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "access")
public class AccessProperties {
    private String defaultRetrievalProfileId = "ret_smoke_01";
    private int stalenessTtlMinutes = 60;
    private int mcpSessionTtlHours = 24;
    private final Cache cache = new Cache();
    private final Retrieval retrieval = new Retrieval();

    public String getDefaultRetrievalProfileId() {
        return defaultRetrievalProfileId;
    }

    public void setDefaultRetrievalProfileId(String defaultRetrievalProfileId) {
        this.defaultRetrievalProfileId = defaultRetrievalProfileId;
    }

    public int getStalenessTtlMinutes() {
        return stalenessTtlMinutes;
    }

    public void setStalenessTtlMinutes(int stalenessTtlMinutes) {
        this.stalenessTtlMinutes = stalenessTtlMinutes;
    }

    public int getMcpSessionTtlHours() {
        return mcpSessionTtlHours;
    }

    public void setMcpSessionTtlHours(int mcpSessionTtlHours) {
        this.mcpSessionTtlHours = mcpSessionTtlHours;
    }

    public Cache getCache() {
        return cache;
    }

    public Retrieval getRetrieval() {
        return retrieval;
    }

    public static class Cache {
        private String provider = "noop";
        private String redisUrl = "redis://127.0.0.1:6379/0";
        private String keyPrefix = "reality-rag:access";
        private int projectionTtlSeconds = 3600;
        private boolean failOpen = true;

        public String getProvider() { return provider; }
        public void setProvider(String provider) { this.provider = provider; }
        public String getRedisUrl() { return redisUrl; }
        public void setRedisUrl(String redisUrl) { this.redisUrl = redisUrl; }
        public String getKeyPrefix() { return keyPrefix; }
        public void setKeyPrefix(String keyPrefix) { this.keyPrefix = keyPrefix; }
        public int getProjectionTtlSeconds() { return projectionTtlSeconds; }
        public void setProjectionTtlSeconds(int projectionTtlSeconds) { this.projectionTtlSeconds = projectionTtlSeconds; }
        public boolean isFailOpen() { return failOpen; }
        public void setFailOpen(boolean failOpen) { this.failOpen = failOpen; }
    }

    public static class Retrieval {
        private String baseUrl = "http://127.0.0.1:18082";
        private Duration connectTimeout = Duration.ofSeconds(1);
        private Duration readTimeout = Duration.ofSeconds(3);

        public String getBaseUrl() {
            return baseUrl;
        }

        public void setBaseUrl(String baseUrl) {
            this.baseUrl = baseUrl;
        }

        public Duration getConnectTimeout() {
            return connectTimeout;
        }

        public void setConnectTimeout(Duration connectTimeout) {
            this.connectTimeout = connectTimeout;
        }

        public Duration getReadTimeout() {
            return readTimeout;
        }

        public void setReadTimeout(Duration readTimeout) {
            this.readTimeout = readTimeout;
        }
    }
}

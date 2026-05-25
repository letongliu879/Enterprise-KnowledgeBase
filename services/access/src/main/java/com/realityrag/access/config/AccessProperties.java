package com.realityrag.access.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "access")
public class AccessProperties {
    private String defaultRetrievalProfileId = "ret_default";
    private final Retrieval retrieval = new Retrieval();

    public String getDefaultRetrievalProfileId() {
        return defaultRetrievalProfileId;
    }

    public void setDefaultRetrievalProfileId(String defaultRetrievalProfileId) {
        this.defaultRetrievalProfileId = defaultRetrievalProfileId;
    }

    public Retrieval getRetrieval() {
        return retrieval;
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

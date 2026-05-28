package com.realityrag.retrieval.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "retrieval.backends")
public class RetrievalBackendProperties {
    private String opensearchBaseUrl;
    private String qdrantBaseUrl;
    private boolean liveRecallEnabled = false;
    private String embeddingBaseUrl;
    private String embeddingApiKey;
    private String embeddingModel;
    private boolean liveEmbeddingEnabled = false;
    private String rerankerBaseUrl;
    private String rerankerApiKey;
    private String rerankerModel;
    private boolean liveRerankEnabled = false;
    private String promptModelBaseUrl;
    private String promptModelApiKey;
    private String promptModelName;
    private boolean livePromptStrategiesEnabled = false;
    private boolean requireLiveBackends = false;

    public String getOpensearchBaseUrl() {
        return opensearchBaseUrl;
    }

    public void setOpensearchBaseUrl(String opensearchBaseUrl) {
        this.opensearchBaseUrl = opensearchBaseUrl;
    }

    public String getQdrantBaseUrl() {
        return qdrantBaseUrl;
    }

    public void setQdrantBaseUrl(String qdrantBaseUrl) {
        this.qdrantBaseUrl = qdrantBaseUrl;
    }

    public boolean isLiveRecallEnabled() {
        return liveRecallEnabled;
    }

    public void setLiveRecallEnabled(boolean liveRecallEnabled) {
        this.liveRecallEnabled = liveRecallEnabled;
    }

    public String getEmbeddingBaseUrl() {
        return embeddingBaseUrl;
    }

    public void setEmbeddingBaseUrl(String embeddingBaseUrl) {
        this.embeddingBaseUrl = embeddingBaseUrl;
    }

    public String getEmbeddingApiKey() {
        return embeddingApiKey;
    }

    public void setEmbeddingApiKey(String embeddingApiKey) {
        this.embeddingApiKey = embeddingApiKey;
    }

    public String getEmbeddingModel() {
        return embeddingModel;
    }

    public void setEmbeddingModel(String embeddingModel) {
        this.embeddingModel = embeddingModel;
    }

    public boolean isLiveEmbeddingEnabled() {
        return liveEmbeddingEnabled;
    }

    public void setLiveEmbeddingEnabled(boolean liveEmbeddingEnabled) {
        this.liveEmbeddingEnabled = liveEmbeddingEnabled;
    }

    public String getRerankerBaseUrl() {
        return rerankerBaseUrl;
    }

    public void setRerankerBaseUrl(String rerankerBaseUrl) {
        this.rerankerBaseUrl = rerankerBaseUrl;
    }

    public String getRerankerApiKey() {
        return rerankerApiKey;
    }

    public void setRerankerApiKey(String rerankerApiKey) {
        this.rerankerApiKey = rerankerApiKey;
    }

    public String getRerankerModel() {
        return rerankerModel;
    }

    public void setRerankerModel(String rerankerModel) {
        this.rerankerModel = rerankerModel;
    }

    public boolean isLiveRerankEnabled() {
        return liveRerankEnabled;
    }

    public void setLiveRerankEnabled(boolean liveRerankEnabled) {
        this.liveRerankEnabled = liveRerankEnabled;
    }

    public String getPromptModelBaseUrl() {
        return promptModelBaseUrl;
    }

    public void setPromptModelBaseUrl(String promptModelBaseUrl) {
        this.promptModelBaseUrl = promptModelBaseUrl;
    }

    public String getPromptModelApiKey() {
        return promptModelApiKey;
    }

    public void setPromptModelApiKey(String promptModelApiKey) {
        this.promptModelApiKey = promptModelApiKey;
    }

    public String getPromptModelName() {
        return promptModelName;
    }

    public void setPromptModelName(String promptModelName) {
        this.promptModelName = promptModelName;
    }

    public boolean isLivePromptStrategiesEnabled() {
        return livePromptStrategiesEnabled;
    }

    public void setLivePromptStrategiesEnabled(boolean livePromptStrategiesEnabled) {
        this.livePromptStrategiesEnabled = livePromptStrategiesEnabled;
    }

    public boolean isRequireLiveBackends() {
        return requireLiveBackends;
    }

    public void setRequireLiveBackends(boolean requireLiveBackends) {
        this.requireLiveBackends = requireLiveBackends;
    }
}

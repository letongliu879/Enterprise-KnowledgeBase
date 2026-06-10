package com.realityrag.access.security;

public interface ApiKeyProjectionCache {
    ApiKeyRegistry.AgentRegistration get(String apiKeyId);
    void set(String apiKeyId, ApiKeyRegistry.AgentRegistration registration);
    void evict(String apiKeyId);
}

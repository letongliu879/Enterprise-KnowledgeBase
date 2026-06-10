package com.realityrag.access.security;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "access.cache.provider", havingValue = "noop", matchIfMissing = true)
public class NoOpApiKeyProjectionCache implements ApiKeyProjectionCache {
    @Override
    public ApiKeyRegistry.AgentRegistration get(String apiKeyId) {
        return null;
    }

    @Override
    public void set(String apiKeyId, ApiKeyRegistry.AgentRegistration registration) {
    }

    @Override
    public void evict(String apiKeyId) {
    }
}

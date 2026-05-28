package com.realityrag.retrieval.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.cache.RetrievalCache;
import com.realityrag.retrieval.cache.RetrievalCacheKeyBuilder;
import com.realityrag.retrieval.cache.RetrievalCacheProperties;
import com.realityrag.retrieval.embedding.CachedQueryEmbeddingClient;
import com.realityrag.retrieval.embedding.OpenAiCompatibleQueryEmbeddingClient;
import com.realityrag.retrieval.embedding.QueryEmbeddingClient;
import com.realityrag.retrieval.embedding.StubQueryEmbeddingClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RetrievalEmbeddingConfiguration {
    @Bean
    public QueryEmbeddingClient queryEmbeddingClient(
        RetrievalBackendProperties backendProperties,
        ObjectMapper objectMapper,
        RetrievalCache cache,
        RetrievalCacheKeyBuilder keyBuilder,
        RetrievalCacheProperties cacheProperties
    ) {
        QueryEmbeddingClient delegate;
        if (backendProperties.isLiveEmbeddingEnabled()) {
            delegate = new OpenAiCompatibleQueryEmbeddingClient(backendProperties, objectMapper);
        } else {
            delegate = new StubQueryEmbeddingClient();
        }
        return new CachedQueryEmbeddingClient(delegate, cache, keyBuilder, cacheProperties, backendProperties);
    }
}

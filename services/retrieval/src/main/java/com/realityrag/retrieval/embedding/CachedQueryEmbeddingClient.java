package com.realityrag.retrieval.embedding;

import com.realityrag.retrieval.cache.RetrievalCache;
import com.realityrag.retrieval.cache.RetrievalCacheKeyBuilder;
import com.realityrag.retrieval.cache.RetrievalCacheProperties;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class CachedQueryEmbeddingClient implements QueryEmbeddingClient {
    private static final Logger LOG = LoggerFactory.getLogger(CachedQueryEmbeddingClient.class);
    private static final String EMBEDDING_CLIENT_TYPE = "openai_compatible";

    private final QueryEmbeddingClient delegate;
    private final RetrievalCache cache;
    private final RetrievalCacheKeyBuilder keyBuilder;
    private final RetrievalCacheProperties cacheProperties;
    private final RetrievalBackendProperties backendProperties;

    public CachedQueryEmbeddingClient(
        QueryEmbeddingClient delegate,
        RetrievalCache cache,
        RetrievalCacheKeyBuilder keyBuilder,
        RetrievalCacheProperties cacheProperties,
        RetrievalBackendProperties backendProperties
    ) {
        this.delegate = delegate;
        this.cache = cache;
        this.keyBuilder = keyBuilder;
        this.cacheProperties = cacheProperties;
        this.backendProperties = backendProperties;
    }

    @Override
    public List<Double> embed(String queryText, String embeddingModel) {
        if (!cacheProperties.isEnabled() || !cache.isAvailable()) {
            return delegate.embed(queryText, embeddingModel);
        }

        String key = keyBuilder.queryEmbeddingKey(
            queryText,
            embeddingModel,
            EMBEDDING_CLIENT_TYPE,
            backendProperties.getEmbeddingBaseUrl()
        );

        @SuppressWarnings("unchecked")
        List<Double> cached = cache.get(key, List.class);
        if (cached != null) {
            LOG.debug("Query embedding cache hit for key={}", key);
            return cached;
        }

        LOG.debug("Query embedding cache miss for key={}", key);
        List<Double> embedding = delegate.embed(queryText, embeddingModel);

        if (embedding != null && !embedding.isEmpty()) {
            cache.set(key, embedding, cacheProperties.getQueryEmbeddingTtlSeconds());
        }

        return embedding;
    }
}

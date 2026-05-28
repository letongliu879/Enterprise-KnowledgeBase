package com.realityrag.retrieval.embedding;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.realityrag.retrieval.cache.RetrievalCache;
import com.realityrag.retrieval.cache.RetrievalCacheKeyBuilder;
import com.realityrag.retrieval.cache.RetrievalCacheProperties;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CachedQueryEmbeddingClientTest {

    private QueryEmbeddingClient delegate;
    private RetrievalCache cache;
    private RetrievalCacheKeyBuilder keyBuilder;
    private RetrievalCacheProperties cacheProperties;
    private RetrievalBackendProperties backendProperties;
    private CachedQueryEmbeddingClient client;

    @BeforeEach
    void setUp() {
        delegate = mock(QueryEmbeddingClient.class);
        cache = mock(RetrievalCache.class);
        keyBuilder = mock(RetrievalCacheKeyBuilder.class);
        cacheProperties = new RetrievalCacheProperties();
        backendProperties = new RetrievalBackendProperties();
        backendProperties.setEmbeddingBaseUrl("https://api.example.com/v1");
        client = new CachedQueryEmbeddingClient(delegate, cache, keyBuilder, cacheProperties, backendProperties);
    }

    @Test
    void whenCacheDisabledDelegatesDirectly() {
        cacheProperties.setEnabled(false);
        List<Double> expected = List.of(0.1, 0.2, 0.3);
        when(delegate.embed("hello", "model-a")).thenReturn(expected);

        List<Double> result = client.embed("hello", "model-a");

        assertEquals(expected, result);
        verify(cache, never()).get(anyString(), org.mockito.ArgumentMatchers.any(Class.class));
        verify(cache, never()).set(anyString(), any(), anyLong());
    }

    @Test
    void whenCacheUnavailableDelegatesDirectly() {
        cacheProperties.setEnabled(true);
        when(cache.isAvailable()).thenReturn(false);
        List<Double> expected = List.of(0.1, 0.2, 0.3);
        when(delegate.embed("hello", "model-a")).thenReturn(expected);

        List<Double> result = client.embed("hello", "model-a");

        assertEquals(expected, result);
        verify(cache, never()).get(anyString(), org.mockito.ArgumentMatchers.any(Class.class));
    }

    @Test
    @SuppressWarnings("unchecked")
    void cacheHitReturnsCachedValueWithoutCallingDelegate() {
        cacheProperties.setEnabled(true);
        when(cache.isAvailable()).thenReturn(true);
        when(keyBuilder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1"))
            .thenReturn("test-key");
        List<Double> cached = List.of(0.4, 0.5, 0.6);
        when(cache.get("test-key", List.class)).thenReturn(cached);

        List<Double> result = client.embed("hello", "model-a");

        assertEquals(cached, result);
        verify(delegate, never()).embed(anyString(), anyString());
    }

    @Test
    @SuppressWarnings("unchecked")
    void cacheMissCallsDelegateAndStoresResult() {
        cacheProperties.setEnabled(true);
        cacheProperties.setQueryEmbeddingTtlSeconds(86400);
        when(cache.isAvailable()).thenReturn(true);
        when(keyBuilder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1"))
            .thenReturn("test-key");
        when(cache.get("test-key", List.class)).thenReturn(null);
        List<Double> embedding = List.of(0.7, 0.8, 0.9);
        when(delegate.embed("hello", "model-a")).thenReturn(embedding);

        List<Double> result = client.embed("hello", "model-a");

        assertEquals(embedding, result);
        verify(delegate).embed("hello", "model-a");
        verify(cache).set("test-key", embedding, 86400);
    }

    @Test
    @SuppressWarnings("unchecked")
    void cacheMissWithEmptyResultDoesNotStore() {
        cacheProperties.setEnabled(true);
        when(cache.isAvailable()).thenReturn(true);
        when(keyBuilder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1"))
            .thenReturn("test-key");
        when(cache.get("test-key", List.class)).thenReturn(null);
        when(delegate.embed("hello", "model-a")).thenReturn(List.of());

        List<Double> result = client.embed("hello", "model-a");

        assertEquals(List.of(), result);
        verify(cache, never()).set(anyString(), any(), anyLong());
    }

    @Test
    @SuppressWarnings("unchecked")
    void cacheMissWithNullResultDoesNotStore() {
        cacheProperties.setEnabled(true);
        when(cache.isAvailable()).thenReturn(true);
        when(keyBuilder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1"))
            .thenReturn("test-key");
        when(cache.get("test-key", List.class)).thenReturn(null);
        when(delegate.embed("hello", "model-a")).thenReturn(null);

        List<Double> result = client.embed("hello", "model-a");

        assertEquals(null, result);
        verify(cache, never()).set(anyString(), any(), anyLong());
    }

    @Test
    @SuppressWarnings("unchecked")
    void differentQueryTextProducesDifferentKeys() {
        cacheProperties.setEnabled(true);
        when(cache.isAvailable()).thenReturn(true);
        when(keyBuilder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1"))
            .thenReturn("key-hello");
        when(keyBuilder.queryEmbeddingKey("world", "model-a", "openai_compatible", "https://api.example.com/v1"))
            .thenReturn("key-world");
        when(cache.get("key-hello", List.class)).thenReturn(null);
        when(cache.get("key-world", List.class)).thenReturn(null);
        when(delegate.embed(anyString(), anyString())).thenReturn(List.of(0.1));

        client.embed("hello", "model-a");
        client.embed("world", "model-a");

        verify(cache).set(eq("key-hello"), any(), anyLong());
        verify(cache).set(eq("key-world"), any(), anyLong());
    }
}

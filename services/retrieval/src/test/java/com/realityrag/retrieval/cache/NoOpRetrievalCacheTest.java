package com.realityrag.retrieval.cache;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.api.Test;

class NoOpRetrievalCacheTest {

    private final NoOpRetrievalCache cache = new NoOpRetrievalCache();

    @Test
    void getAlwaysReturnsNull() {
        assertNull(cache.get("any-key", String.class));
        assertNull(cache.get("any-key", Integer.class));
    }

    @Test
    void getWithTypeReferenceReturnsNull() {
        assertNull(cache.get("any-key", new com.fasterxml.jackson.core.type.TypeReference<java.util.List<String>>() {}));
    }

    @Test
    void setDoesNotThrow() {
        cache.set("key", "value", 60);
        assertNull(cache.get("key", String.class));
    }

    @Test
    void deleteReturnsFalse() {
        assertFalse(cache.delete("key"));
    }

    @Test
    void deleteByPatternReturnsZero() {
        assertEquals(0, cache.deleteByPattern("*"));
    }

    @Test
    void isAvailableReturnsFalse() {
        assertFalse(cache.isAvailable());
    }
}

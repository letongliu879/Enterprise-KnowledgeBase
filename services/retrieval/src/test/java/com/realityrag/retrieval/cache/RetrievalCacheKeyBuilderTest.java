package com.realityrag.retrieval.cache;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrievalScope;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class RetrievalCacheKeyBuilderTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final RetrievalCacheProperties properties = new RetrievalCacheProperties();
    private final RetrievalCacheKeyBuilder builder = new RetrievalCacheKeyBuilder(properties, objectMapper);

    @Test
    void queryEmbeddingKeyIsStableForSameInputs() {
        String key1 = builder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1");
        String key2 = builder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1");
        assertEquals(key1, key2);
    }

    @Test
    void queryEmbeddingKeyChangesWhenQueryChanges() {
        String key1 = builder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1");
        String key2 = builder.queryEmbeddingKey("world", "model-a", "openai_compatible", "https://api.example.com/v1");
        assertNotEquals(key1, key2);
    }

    @Test
    void queryEmbeddingKeyChangesWhenModelChanges() {
        String key1 = builder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1");
        String key2 = builder.queryEmbeddingKey("hello", "model-b", "openai_compatible", "https://api.example.com/v1");
        assertNotEquals(key1, key2);
    }

    @Test
    void queryEmbeddingKeyChangesWhenBaseUrlChanges() {
        String key1 = builder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1");
        String key2 = builder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.other.com/v1");
        assertNotEquals(key1, key2);
    }

    @Test
    void queryEmbeddingKeyIgnoresTrailingSlashes() {
        String key1 = builder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1/");
        String key2 = builder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1");
        assertEquals(key1, key2);
    }

    @Test
    void queryEmbeddingKeyFormatIsCorrect() {
        String key = builder.queryEmbeddingKey("hello", "model-a", "openai_compatible", "https://api.example.com/v1");
        assertTrue(key.startsWith("reality-rag:retrieval:qemb:v1:"));
        assertEquals(64 + "reality-rag:retrieval:qemb:v1:".length(), key.length());
    }

    @Test
    void recallKeyIsStableForSameInputs() {
        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        String key1 = builder.recallKey(scope, plans, "hello", 20);
        String key2 = builder.recallKey(scope, plans, "hello", 20);
        assertEquals(key1, key2);
    }

    @Test
    void recallKeyChangesWhenQueryChanges() {
        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        String key1 = builder.recallKey(scope, plans, "hello", 20);
        String key2 = builder.recallKey(scope, plans, "world", 20);
        assertNotEquals(key1, key2);
    }

    @Test
    void recallKeyChangesWhenIndexVersionChanges() {
        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans1 = List.of(buildPlan("col_a", "idxv_1"));
        List<CollectionRetrievalPlan> plans2 = List.of(buildPlan("col_a", "idxv_2"));
        String key1 = builder.recallKey(scope, plans1, "hello", 20);
        String key2 = builder.recallKey(scope, plans2, "hello", 20);
        assertNotEquals(key1, key2);
    }

    @Test
    void recallKeyChangesWhenProfileHashChanges() {
        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans1 = List.of(buildPlanWithHash("col_a", "hash_a"));
        List<CollectionRetrievalPlan> plans2 = List.of(buildPlanWithHash("col_a", "hash_b"));
        String key1 = builder.recallKey(scope, plans1, "hello", 20);
        String key2 = builder.recallKey(scope, plans2, "hello", 20);
        assertNotEquals(key1, key2);
    }

    @Test
    void recallKeyIsIndependentOfCollectionOrder() {
        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans1 = List.of(
            buildPlan("col_a", "idxv_1"),
            buildPlan("col_b", "idxv_2")
        );
        List<CollectionRetrievalPlan> plans2 = List.of(
            buildPlan("col_b", "idxv_2"),
            buildPlan("col_a", "idxv_1")
        );
        String key1 = builder.recallKey(scope, plans1, "hello", 20);
        String key2 = builder.recallKey(scope, plans2, "hello", 20);
        assertEquals(key1, key2);
    }

    @Test
    void recallKeyFormatIsCorrect() {
        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        String key = builder.recallKey(scope, plans, "hello", 20);
        assertTrue(key.startsWith("reality-rag:retrieval:recall:v1:"));
        assertEquals(64 + "reality-rag:retrieval:recall:v1:".length(), key.length());
    }

    private RetrievalScope buildScope() {
        return new RetrievalScope(
            "usr_1",
            List.of("col_a"),
            List.of("doc_1"),
            Map.of("principal_groups", List.of("finance")),
            false,
            "perm:usr_1:col_a",
            List.of()
        );
    }

    private List<CollectionRetrievalPlan> buildPlans() {
        return List.of(buildPlan("col_a", "idxv_1"));
    }

    private CollectionRetrievalPlan buildPlan(String collectionId, String indexVersionId) {
        return new CollectionRetrievalPlan(
            "tnt_default",
            collectionId,
            indexVersionId,
            "os_" + collectionId,
            "qd_" + collectionId,
            "model-a",
            "chunk_default",
            Map.of("candidate_top_k", 20),
            "ret_default",
            1,
            "hash_" + indexVersionId,
            Map.of(),
            Map.of(),
            false,
            List.of("doc_1"),
            Map.of()
        );
    }

    private CollectionRetrievalPlan buildPlanWithHash(String collectionId, String profileHash) {
        return new CollectionRetrievalPlan(
            "tnt_default",
            collectionId,
            "idxv_1",
            "os_" + collectionId,
            "qd_" + collectionId,
            "model-a",
            "chunk_default",
            Map.of("candidate_top_k", 20),
            "ret_default",
            1,
            profileHash,
            Map.of(),
            Map.of(),
            false,
            List.of("doc_1"),
            Map.of()
        );
    }
}

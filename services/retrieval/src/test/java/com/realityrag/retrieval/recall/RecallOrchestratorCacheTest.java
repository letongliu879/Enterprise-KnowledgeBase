package com.realityrag.retrieval.recall;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.core.type.TypeReference;
import com.realityrag.retrieval.cache.RetrievalCache;
import com.realityrag.retrieval.cache.RetrievalCacheKeyBuilder;
import com.realityrag.retrieval.cache.RetrievalCacheProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrievalScope;
import com.realityrag.retrieval.fusion.HybridFusionService;
import com.realityrag.retrieval.permission.PermissionPrefilter;
import com.realityrag.retrieval.recall.BackendRecallHit;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.store.KnowledgeStore;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class RecallOrchestratorCacheTest {

    private KnowledgeStore knowledgeStore;
    private PermissionPrefilter permissionPrefilter;
    private HybridRecaller hybridRecaller;
    private HybridFusionService hybridFusionService;
    private RetrievalCache cache;
    private RetrievalCacheKeyBuilder keyBuilder;
    private RetrievalCacheProperties cacheProperties;
    private RecallOrchestrator orchestrator;

    @BeforeEach
    void setUp() {
        knowledgeStore = mock(KnowledgeStore.class);
        permissionPrefilter = mock(PermissionPrefilter.class);
        hybridRecaller = mock(HybridRecaller.class);
        hybridFusionService = new HybridFusionService();
        cache = mock(RetrievalCache.class);
        keyBuilder = mock(RetrievalCacheKeyBuilder.class);
        cacheProperties = new RetrievalCacheProperties();
        orchestrator = new RecallOrchestrator(
            knowledgeStore, permissionPrefilter, hybridRecaller,
            hybridFusionService, cache, keyBuilder, cacheProperties
        );
    }

    @Test
    @SuppressWarnings("unchecked")
    void cacheHitReturnsCachedCandidatesWithoutCallingBackends() {
        cacheProperties.setEnabled(true);
        when(cache.isAvailable()).thenReturn(true);
        when(keyBuilder.recallKey(any(), anyList(), anyString(), anyInt())).thenReturn("recall-key");
        List<RetrievedChunk> cached = List.of(
            new RetrievedChunk(chunk("chk_1"), 0.9, "hybrid_fusion", "cached")
        );
        when(cache.get(anyString(), any(TypeReference.class))).thenReturn(cached);

        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        List<RetrievedChunk> result = orchestrator.recall(scope, plans, "query");

        assertEquals(1, result.size());
        assertEquals("chk_1", result.get(0).chunk().chunkId());
        verify(hybridRecaller, never()).recallLexical(any(), any(), anyString());
        verify(hybridRecaller, never()).recallVector(any(), any(), anyString());
    }

    @Test
    @SuppressWarnings("unchecked")
    void cacheMissExecutesBackendsAndStoresResult() {
        cacheProperties.setEnabled(true);
        cacheProperties.setRecallTtlSeconds(60);
        when(cache.isAvailable()).thenReturn(true);
        when(keyBuilder.recallKey(any(), anyList(), anyString(), anyInt())).thenReturn("recall-key");
        when(cache.get(anyString(), any(TypeReference.class))).thenReturn(null);

        IndexedChunk permittedChunk = chunk("chk_1");
        when(knowledgeStore.listChunks("col_a", "idxv_1")).thenReturn(List.of(permittedChunk));
        when(permissionPrefilter.filter(any(), anyList())).thenReturn(List.of(permittedChunk));
        when(hybridRecaller.recallLexical(any(), anyList(), anyString()))
            .thenReturn(List.of(new BackendRecallHit(permittedChunk, 0.8, "opensearch", "match")));
        when(hybridRecaller.recallVector(any(), anyList(), anyString())).thenReturn(List.of());

        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        List<RetrievedChunk> result = orchestrator.recall(scope, plans, "query");

        assertEquals(1, result.size());
        assertEquals("chk_1", result.get(0).chunk().chunkId());
        verify(cache).set(eq("recall-key"), anyList(), eq(60L));
    }

    @Test
    void whenCacheDisabledExecutesBackendsWithoutCache() {
        cacheProperties.setEnabled(false);

        IndexedChunk permittedChunk = chunk("chk_1");
        when(knowledgeStore.listChunks("col_a", "idxv_1")).thenReturn(List.of(permittedChunk));
        when(permissionPrefilter.filter(any(), anyList())).thenReturn(List.of(permittedChunk));
        when(hybridRecaller.recallLexical(any(), anyList(), anyString()))
            .thenReturn(List.of(new BackendRecallHit(permittedChunk, 0.8, "opensearch", "match")));
        when(hybridRecaller.recallVector(any(), anyList(), anyString())).thenReturn(List.of());

        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        List<RetrievedChunk> result = orchestrator.recall(scope, plans, "query");

        assertEquals(1, result.size());
        verify(cache, never()).get(anyString(), any(TypeReference.class));
        verify(cache, never()).set(anyString(), any(), anyLong());
    }

    @Test
    void whenCacheUnavailableExecutesBackendsWithoutCache() {
        cacheProperties.setEnabled(true);
        when(cache.isAvailable()).thenReturn(false);

        IndexedChunk permittedChunk = chunk("chk_1");
        when(knowledgeStore.listChunks("col_a", "idxv_1")).thenReturn(List.of(permittedChunk));
        when(permissionPrefilter.filter(any(), anyList())).thenReturn(List.of(permittedChunk));
        when(hybridRecaller.recallLexical(any(), anyList(), anyString()))
            .thenReturn(List.of(new BackendRecallHit(permittedChunk, 0.8, "opensearch", "match")));
        when(hybridRecaller.recallVector(any(), anyList(), anyString())).thenReturn(List.of());

        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        List<RetrievedChunk> result = orchestrator.recall(scope, plans, "query");

        assertEquals(1, result.size());
        verify(cache, never()).get(anyString(), any(TypeReference.class));
        verify(cache, never()).set(anyString(), any(), anyLong());
    }

    @Test
    void intersectWithPermittedFiltersOutUnauthorizedBackendHits() {
        cacheProperties.setEnabled(false);

        IndexedChunk permittedChunk = chunk("chk_1");
        IndexedChunk unauthorizedChunk = chunk("chk_2");
        when(knowledgeStore.listChunks("col_a", "idxv_1"))
            .thenReturn(List.of(permittedChunk, unauthorizedChunk));
        when(permissionPrefilter.filter(any(), anyList())).thenReturn(List.of(permittedChunk));

        // Backend returns both chunks, but only chk_1 is in permitted list
        when(hybridRecaller.recallLexical(any(), anyList(), anyString()))
            .thenReturn(List.of(
                new BackendRecallHit(permittedChunk, 0.8, "opensearch", "match"),
                new BackendRecallHit(unauthorizedChunk, 0.7, "opensearch", "match")
            ));
        when(hybridRecaller.recallVector(any(), anyList(), anyString())).thenReturn(List.of());

        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        List<RetrievedChunk> result = orchestrator.recall(scope, plans, "query");

        assertEquals(1, result.size());
        assertEquals("chk_1", result.get(0).chunk().chunkId());
    }

    @Test
    void intersectWithPermittedReturnsEmptyWhenNoPermittedChunks() {
        cacheProperties.setEnabled(false);

        when(knowledgeStore.listChunks("col_a", "idxv_1")).thenReturn(List.of());
        when(permissionPrefilter.filter(any(), anyList())).thenReturn(List.of());
        when(hybridRecaller.recallLexical(any(), anyList(), anyString())).thenReturn(List.of());
        when(hybridRecaller.recallVector(any(), anyList(), anyString())).thenReturn(List.of());

        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        List<RetrievedChunk> result = orchestrator.recall(scope, plans, "query");

        assertTrue(result.isEmpty());
    }

    @Test
    void intersectWithPermittedHandlesBackendReturningChunksNotInPermittedSet() {
        cacheProperties.setEnabled(false);

        IndexedChunk permittedChunk = chunk("chk_1");
        IndexedChunk backendOnlyChunk = chunk("chk_backend_only");
        when(knowledgeStore.listChunks("col_a", "idxv_1")).thenReturn(List.of(permittedChunk));
        when(permissionPrefilter.filter(any(), anyList())).thenReturn(List.of(permittedChunk));

        // Qdrant returns a chunk that was never in the permitted list
        when(hybridRecaller.recallLexical(any(), anyList(), anyString())).thenReturn(List.of());
        when(hybridRecaller.recallVector(any(), anyList(), anyString()))
            .thenReturn(List.of(
                new BackendRecallHit(backendOnlyChunk, 0.95, "qdrant", "match")
            ));

        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans = buildPlans();
        List<RetrievedChunk> result = orchestrator.recall(scope, plans, "query");

        assertTrue(result.isEmpty());
    }

    @Test
    @SuppressWarnings("unchecked")
    void differentPlanProducesDifferentCacheKey() {
        cacheProperties.setEnabled(true);
        when(cache.isAvailable()).thenReturn(true);
        when(keyBuilder.recallKey(any(), anyList(), anyString(), anyInt())).thenReturn("key-1", "key-2");
        when(cache.get(anyString(), any(TypeReference.class))).thenReturn(null);

        IndexedChunk chunk = chunk("chk_1");
        when(knowledgeStore.listChunks(anyString(), anyString())).thenReturn(List.of(chunk));
        when(permissionPrefilter.filter(any(), anyList())).thenReturn(List.of(chunk));
        when(hybridRecaller.recallLexical(any(), anyList(), anyString()))
            .thenReturn(List.of(new BackendRecallHit(chunk, 0.8, "opensearch", "match")));
        when(hybridRecaller.recallVector(any(), anyList(), anyString())).thenReturn(List.of());

        RetrievalScope scope = buildScope();
        List<CollectionRetrievalPlan> plans1 = List.of(buildPlan("col_a", "idxv_1"));
        List<CollectionRetrievalPlan> plans2 = List.of(buildPlan("col_a", "idxv_2"));

        orchestrator.recall(scope, plans1, "query");
        orchestrator.recall(scope, plans2, "query");

        verify(cache).set(eq("key-1"), anyList(), anyLong());
        verify(cache).set(eq("key-2"), anyList(), anyLong());
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

    private IndexedChunk chunk(String chunkId) {
        return new IndexedChunk(
            "col_a",
            "doc_1",
            "idxv_1",
            "dir_1",
            chunkId,
            "display text",
            "vector text",
            List.of(),
            List.of(),
            "PUBLISHED",
            "internal",
            List.of(),
            List.of("finance"),
            Map.of(),
            Map.of()
        );
    }
}

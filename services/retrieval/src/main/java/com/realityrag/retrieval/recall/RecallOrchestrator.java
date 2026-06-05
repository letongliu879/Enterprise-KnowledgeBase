package com.realityrag.retrieval.recall;

import com.realityrag.retrieval.cache.RetrievalCache;
import com.realityrag.retrieval.cache.RetrievalCacheKeyBuilder;
import com.realityrag.retrieval.cache.RetrievalCacheProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrievalScope;
import com.realityrag.retrieval.fusion.HybridFusionService;
import com.realityrag.retrieval.permission.PermissionPrefilter;
import com.realityrag.retrieval.recall.HybridRecaller;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.store.KnowledgeStore;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class RecallOrchestrator {
    private static final Logger LOG = LoggerFactory.getLogger(RecallOrchestrator.class);
    private static final com.fasterxml.jackson.core.type.TypeReference<List<RetrievedChunk>> CHUNK_LIST_TYPE =
        new com.fasterxml.jackson.core.type.TypeReference<List<RetrievedChunk>>() {};

    private final KnowledgeStore knowledgeStore;
    private final PermissionPrefilter permissionPrefilter;
    private final HybridRecaller hybridRecaller;
    private final HybridFusionService hybridFusionService;
    private final RetrievalCache cache;
    private final RetrievalCacheKeyBuilder keyBuilder;
    private final RetrievalCacheProperties cacheProperties;

    public RecallOrchestrator(
        KnowledgeStore knowledgeStore,
        PermissionPrefilter permissionPrefilter,
        HybridRecaller hybridRecaller,
        HybridFusionService hybridFusionService,
        RetrievalCache cache,
        RetrievalCacheKeyBuilder keyBuilder,
        RetrievalCacheProperties cacheProperties
    ) {
        this.knowledgeStore = knowledgeStore;
        this.permissionPrefilter = permissionPrefilter;
        this.hybridRecaller = hybridRecaller;
        this.hybridFusionService = hybridFusionService;
        this.cache = cache;
        this.keyBuilder = keyBuilder;
        this.cacheProperties = cacheProperties;
    }

    public List<RetrievedChunk> recall(RetrievalScope scope, List<CollectionRetrievalPlan> plans, String queryText) {
        if (cacheProperties.isEnabled() && cache.isAvailable()) {
            String key = keyBuilder.recallKey(scope, plans, queryText, candidateTopK());
            List<RetrievedChunk> cached = cache.get(key, CHUNK_LIST_TYPE);
            if (cached != null) {
                LOG.debug("Recall cache hit for key={}", key);
                return cached;
            }
            LOG.debug("Recall cache miss for key={}", key);
            List<RetrievedChunk> result = executeRecall(scope, plans, queryText);
            cache.set(key, result, cacheProperties.getRecallTtlSeconds());
            return result;
        }
        return executeRecall(scope, plans, queryText);
    }

    private List<RetrievedChunk> executeRecall(RetrievalScope scope, List<CollectionRetrievalPlan> plans, String queryText) {
        List<RetrievedChunk> recalled = new ArrayList<>();
        for (CollectionRetrievalPlan plan : plans) {
            RetrievalScope scopeForPlan = new RetrievalScope(
                scope.principalId(),
                List.of(plan.collectionId()),
                scope.allowedDocIds(),
                mergeFilters(scope.metadataFilters(), plan.lifecycleFilter()),
                plan.includeDeprecated(),
                scope.permissionFingerprint(),
                List.of(plan)
            );
            List<IndexedChunk> filteredChunks = permissionPrefilter.filter(
                scopeForPlan,
                knowledgeStore.listChunks(plan.collectionId(), plan.activeIndexVersionId())
            );
            List<BackendRecallHit> backendHits = new ArrayList<>();
            backendHits.addAll(hybridRecaller.recallLexical(plan, filteredChunks, queryText));
            backendHits.addAll(hybridRecaller.recallVector(plan, filteredChunks, queryText));

            List<BackendRecallHit> permittedHits = intersectWithPermitted(backendHits, filteredChunks);

            for (BackendRecallHit hit : hybridFusionService.fuse(permittedHits)) {
                recalled.add(new RetrievedChunk(
                    hit.chunk(),
                    hit.score(),
                    "hybrid_fusion:" + hit.backendName(),
                    hit.whySelected()
                ));
            }
        }
        return recalled.stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .toList();
    }

    private List<BackendRecallHit> intersectWithPermitted(List<BackendRecallHit> backendHits, List<IndexedChunk> permittedChunks) {
        if (permittedChunks.isEmpty()) {
            return List.of();
        }
        Set<String> permittedChunkIds = permittedChunks.stream()
            .map(IndexedChunk::chunkId)
            .collect(Collectors.toSet());
        return backendHits.stream()
            .filter(hit -> permittedChunkIds.contains(hit.chunk().chunkId()))
            .toList();
    }

    private int candidateTopK() {
        return 20;
    }

    private Map<String, Object> mergeFilters(Map<String, Object> metadataFilters, Map<String, Object> lifecycleFilter) {
        LinkedHashMap<String, Object> merged = new LinkedHashMap<>(metadataFilters);
        merged.putAll(lifecycleFilter);
        return merged;
    }
}

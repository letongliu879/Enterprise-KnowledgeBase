package com.realityrag.retrieval.recall;

import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrievalScope;
import com.realityrag.retrieval.fusion.HybridFusionService;
import com.realityrag.retrieval.permission.PermissionPrefilter;
import com.realityrag.retrieval.recall.backends.BackendRecallHit;
import com.realityrag.retrieval.recall.backends.OpenSearchRecaller;
import com.realityrag.retrieval.recall.backends.QdrantRecaller;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.store.KnowledgeStore;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class RecallOrchestrator {
    private final KnowledgeStore knowledgeStore;
    private final PermissionPrefilter permissionPrefilter;
    private final OpenSearchRecaller openSearchRecaller;
    private final QdrantRecaller qdrantRecaller;
    private final HybridFusionService hybridFusionService;

    public RecallOrchestrator(
        KnowledgeStore knowledgeStore,
        PermissionPrefilter permissionPrefilter,
        OpenSearchRecaller openSearchRecaller,
        QdrantRecaller qdrantRecaller,
        HybridFusionService hybridFusionService
    ) {
        this.knowledgeStore = knowledgeStore;
        this.permissionPrefilter = permissionPrefilter;
        this.openSearchRecaller = openSearchRecaller;
        this.qdrantRecaller = qdrantRecaller;
        this.hybridFusionService = hybridFusionService;
    }

    public List<RetrievedChunk> recall(RetrievalScope scope, List<CollectionRetrievalPlan> plans, String queryText) {
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
                knowledgeStore.listChunks(plan.collectionId())
            );
            List<BackendRecallHit> backendHits = new ArrayList<>();
            backendHits.addAll(openSearchRecaller.recall(plan, filteredChunks, queryText));
            backendHits.addAll(qdrantRecaller.recall(plan, filteredChunks, queryText));
            List<RetrievedChunk> fusedChunks = new ArrayList<>();
            for (BackendRecallHit hit : hybridFusionService.fuse(backendHits)) {
                fusedChunks.add(new RetrievedChunk(
                    hit.chunk(),
                    hit.score(),
                    "hybrid_recall_stub",
                    hit.whySelected()
                ));
            }
            for (RetrievedChunk hit : fusedChunks) {
                recalled.add(new RetrievedChunk(
                    hit.chunk(),
                    hit.score(),
                    "hybrid_fusion",
                    hit.whySelected()
                ));
            }
        }
        return recalled.stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .toList();
    }

    private Map<String, Object> mergeFilters(Map<String, Object> metadataFilters, Map<String, Object> lifecycleFilter) {
        java.util.LinkedHashMap<String, Object> merged = new java.util.LinkedHashMap<>(metadataFilters);
        merged.putAll(lifecycleFilter);
        return merged;
    }
}

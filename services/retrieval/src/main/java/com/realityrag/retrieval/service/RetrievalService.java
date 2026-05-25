package com.realityrag.retrieval.service;

import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.KnowledgeContext;
import com.realityrag.retrieval.contracts.RetrievalScope;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.cutoff.SmartTopKCutoffService;
import com.realityrag.retrieval.expansion.BreadcrumbChunkExpander;
import com.realityrag.retrieval.expansion.NeighborChunkExpander;
import com.realityrag.retrieval.packing.KnowledgeContextPacker;
import com.realityrag.retrieval.preprocess.QueryPreparationService;
import com.realityrag.retrieval.preprocess.QueryPreparationService.PreparedQuery;
import com.realityrag.retrieval.recall.RecallOrchestrator;
import com.realityrag.retrieval.recall.RetrievedChunk;
import com.realityrag.retrieval.ragflow.RagflowChildrenAggregationService;
import com.realityrag.retrieval.ragflow.RagflowTocAggregationService;
import com.realityrag.retrieval.rerank.RerankService;
import com.realityrag.retrieval.scope.CollectionRetrievalPlanBuilder;
import com.realityrag.retrieval.trace.RetrievalTraceRecorder;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;

@Service
public class RetrievalService {
    private final CollectionRetrievalPlanBuilder planBuilder;
    private final QueryPreparationService queryPreparationService;
    private final RecallOrchestrator recallOrchestrator;
    private final RerankService rerankService;
    private final SmartTopKCutoffService smartTopKCutoffService;
    private final NeighborChunkExpander neighborChunkExpander;
    private final BreadcrumbChunkExpander breadcrumbChunkExpander;
    private final RagflowTocAggregationService ragflowTocAggregationService;
    private final RagflowChildrenAggregationService ragflowChildrenAggregationService;
    private final KnowledgeContextPacker knowledgeContextPacker;
    private final RetrievalTraceRecorder retrievalTraceRecorder;

    public RetrievalService(
        CollectionRetrievalPlanBuilder planBuilder,
        QueryPreparationService queryPreparationService,
        RecallOrchestrator recallOrchestrator,
        RerankService rerankService,
        SmartTopKCutoffService smartTopKCutoffService,
        NeighborChunkExpander neighborChunkExpander,
        BreadcrumbChunkExpander breadcrumbChunkExpander,
        RagflowTocAggregationService ragflowTocAggregationService,
        RagflowChildrenAggregationService ragflowChildrenAggregationService,
        KnowledgeContextPacker knowledgeContextPacker,
        RetrievalTraceRecorder retrievalTraceRecorder
    ) {
        this.planBuilder = planBuilder;
        this.queryPreparationService = queryPreparationService;
        this.recallOrchestrator = recallOrchestrator;
        this.rerankService = rerankService;
        this.smartTopKCutoffService = smartTopKCutoffService;
        this.neighborChunkExpander = neighborChunkExpander;
        this.breadcrumbChunkExpander = breadcrumbChunkExpander;
        this.ragflowTocAggregationService = ragflowTocAggregationService;
        this.ragflowChildrenAggregationService = ragflowChildrenAggregationService;
        this.knowledgeContextPacker = knowledgeContextPacker;
        this.retrievalTraceRecorder = retrievalTraceRecorder;
    }

    public KnowledgeContext retrieve(RetrieveRequest request) {
        List<CollectionRetrievalPlan> plans = List.of();
        try {
            plans = planBuilder.build(request);
            PreparedQuery preparedQuery = queryPreparationService.prepare(request, plans);
            RetrievalScope scope = buildScope(request, plans, preparedQuery.allowedDocIds());
            List<RetrievedChunk> fusedCandidates = recallOrchestrator.recall(scope, plans, preparedQuery.queryText());
            List<RetrievedChunk> rerankedCandidates = rerankService.rerank(preparedQuery.queryText(), plans, fusedCandidates);
            List<RetrievedChunk> seeds = smartTopKCutoffService.selectSeeds(rerankedCandidates);
            List<RetrievedChunk> expanded = new ArrayList<>(neighborChunkExpander.expand(seeds));
            expanded.addAll(breadcrumbChunkExpander.expand(seeds));
            List<RetrievedChunk> finalChunks = new ArrayList<>(seeds);
            finalChunks.addAll(expanded);
            finalChunks = new ArrayList<>(ragflowTocAggregationService.aggregate(preparedQuery.queryText(), finalChunks));
            finalChunks = new ArrayList<>(ragflowChildrenAggregationService.aggregate(finalChunks));
            String debugRef = retrievalTraceRecorder.record(request, plans, finalChunks);
            return knowledgeContextPacker.pack(request, scope, plans, finalChunks, debugRef);
        }
        catch (RuntimeException error) {
            retrievalTraceRecorder.recordFailure(request, plans, error);
            throw error;
        }
    }

    private RetrievalScope buildScope(RetrieveRequest request, List<CollectionRetrievalPlan> plans, List<String> allowedDocIdsOverride) {
        Map<String, Object> metadataFilters = new LinkedHashMap<>(request.filters());
        metadataFilters.put("principal_groups", request.principal().groups());
        metadataFilters.put(
            "embedding_model_groups",
            plans.stream().collect(Collectors.groupingBy(
                CollectionRetrievalPlan::embeddingModel,
                LinkedHashMap::new,
                Collectors.mapping(CollectionRetrievalPlan::collectionId, Collectors.toList())))
        );

        List<String> allowedDocIds = new ArrayList<>();
        for (CollectionRetrievalPlan plan : plans) {
            allowedDocIds.addAll(plan.allowedDocIds());
        }
        if (allowedDocIdsOverride != null && !allowedDocIdsOverride.isEmpty()) {
            allowedDocIds.retainAll(new java.util.LinkedHashSet<>(allowedDocIdsOverride));
        }

        return new RetrievalScope(
            request.principal().principalId(),
            request.collectionScope(),
            allowedDocIds,
            metadataFilters,
            request.includeDeprecated(),
            buildPermissionFingerprint(request),
            plans
        );
    }

    private String buildPermissionFingerprint(RetrieveRequest request) {
        String joinedCollections = request.collectionScope().stream().sorted().collect(Collectors.joining(","));
        return "perm:" + request.principal().principalId() + ":" + joinedCollections;
    }
}

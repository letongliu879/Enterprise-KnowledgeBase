package com.realityrag.retrieval.packing;

import com.realityrag.retrieval.config.RetrievalSearchStrategyProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.KnowledgeContext;
import com.realityrag.retrieval.contracts.RetrievalScope;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.recall.RetrievedChunk;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

@Component
public class KnowledgeContextPacker {
    private final RetrievalSearchStrategyProperties strategyProperties;

    public KnowledgeContextPacker(RetrievalSearchStrategyProperties strategyProperties) {
        this.strategyProperties = strategyProperties;
    }

    public KnowledgeContext pack(
        RetrieveRequest request,
        RetrievalScope scope,
        List<CollectionRetrievalPlan> plans,
        List<RetrievedChunk> retrievedChunks,
        String debugRef
    ) {
        List<KnowledgeContext.ResultChunk> resultChunks = applyPackingBudget(retrievedChunks).stream()
            .map(item -> new KnowledgeContext.ResultChunk(
                item.chunk().collectionId(),
                item.chunk().finalDocId(),
                item.chunk().chunkId(),
                item.chunk().documentIndexRevisionId(),
                item.chunk().displayText(),
                item.chunk().sectionPath(),
                item.chunk().pageSpans(),
                item.score(),
                item.sourceStage(),
                item.whySelected()
            ))
            .toList();

        List<Map<String, Object>> groupedSources = retrievedChunks.stream()
            .collect(Collectors.toMap(
                item -> item.chunk().collectionId() + "::" + item.chunk().finalDocId(),
                item -> Map.<String, Object>of(
                    "collection_id", item.chunk().collectionId(),
                    "final_doc_id", item.chunk().finalDocId()
                ),
                (left, right) -> left,
                LinkedHashMap::new
            ))
            .values()
            .stream()
            .toList();

        List<Map<String, Object>> citations = retrievedChunks.stream()
            .map(item -> item.chunk().citationPayload())
            .toList();

        List<String> indexVersionsUsed = retrievedChunks.isEmpty()
            ? plans.stream().map(CollectionRetrievalPlan::activeIndexVersionId).distinct().toList()
            : retrievedChunks.stream().map(item -> item.chunk().indexVersionId()).distinct().toList();

        int computedBudget = resultChunks.stream()
            .mapToInt(chunk -> Math.min(chunk.displayText().length(), 256))
            .sum();
        int appliedBudget = request.maxContextTokens() == null ? computedBudget : Math.min(request.maxContextTokens(), computedBudget);

        return new KnowledgeContext(
            request.queryId(),
            Map.of(
                "principal_id", request.principal().principalId(),
                "permission_fingerprint", scope.permissionFingerprint()
            ),
            indexVersionsUsed,
            plans,
            resultChunks,
            groupedSources,
            citations,
            appliedBudget,
            Map.of(
                "debug_level", request.debugLevel(),
                "debug_ref", debugRef,
                "packing", Map.of(
                    "max_segments_per_file", strategyProperties.getMaxSegmentsPerFile(),
                    "max_total_chars", strategyProperties.getMaxTotalChars()
                )
            )
        );
    }

    private List<RetrievedChunk> applyPackingBudget(List<RetrievedChunk> retrievedChunks) {
        Map<String, List<RetrievedChunk>> byFile = retrievedChunks.stream()
            .collect(Collectors.groupingBy(
                item -> item.chunk().collectionId() + "::" + item.chunk().finalDocId(),
                LinkedHashMap::new,
                Collectors.toList()
            ));

        List<RetrievedChunk> packed = new ArrayList<>();
        int totalChars = 0;

        for (List<RetrievedChunk> fileChunks : byFile.values()) {
            List<RetrievedChunk> sortedPerFile = fileChunks.stream()
                .sorted(java.util.Comparator.comparingDouble(RetrievedChunk::score).reversed())
                .limit(strategyProperties.getMaxSegmentsPerFile())
                .toList();

            for (RetrievedChunk chunk : sortedPerFile) {
                int nextChars = Math.min(chunk.chunk().displayText().length(), 2048);
                if (totalChars + nextChars > strategyProperties.getMaxTotalChars()) {
                    return packed;
                }
                packed.add(chunk);
                totalChars += nextChars;
            }
        }

        return packed;
    }
}

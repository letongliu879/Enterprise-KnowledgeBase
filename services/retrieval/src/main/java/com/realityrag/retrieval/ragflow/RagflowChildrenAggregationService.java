package com.realityrag.retrieval.ragflow;

import com.realityrag.retrieval.config.RetrievalSearchStrategyProperties;
import com.realityrag.retrieval.recall.RetrievedChunk;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.store.KnowledgeStore;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class RagflowChildrenAggregationService {
    private final KnowledgeStore knowledgeStore;
    private final RetrievalSearchStrategyProperties strategyProperties;

    public RagflowChildrenAggregationService(
        KnowledgeStore knowledgeStore,
        RetrievalSearchStrategyProperties strategyProperties
    ) {
        this.knowledgeStore = knowledgeStore;
        this.strategyProperties = strategyProperties;
    }

    public List<RetrievedChunk> aggregate(List<RetrievedChunk> chunks) {
        if (!strategyProperties.isEnableRagflowChildrenAggregation() || chunks.isEmpty()) {
            return chunks;
        }

        List<RetrievedChunk> remaining = new ArrayList<>();
        Map<String, List<RetrievedChunk>> byParentChunk = new LinkedHashMap<>();
        for (RetrievedChunk chunk : chunks) {
            String parentChunkId = parentChunkId(chunk);
            if (parentChunkId == null) {
                remaining.add(chunk);
                continue;
            }
            byParentChunk.computeIfAbsent(parentChunkId, ignored -> new ArrayList<>()).add(chunk);
        }

        if (byParentChunk.isEmpty()) {
            return chunks;
        }

        Map<String, RetrievedChunk> deduped = new LinkedHashMap<>();
        for (RetrievedChunk chunk : remaining) {
            deduped.put(chunk.chunk().chunkId(), chunk);
        }
        for (Map.Entry<String, List<RetrievedChunk>> entry : byParentChunk.entrySet()) {
            List<RetrievedChunk> childChunks = entry.getValue();
            IndexedChunk parent = lookupParentChunk(entry.getKey(), childChunks.get(0));
            if (parent == null) {
                for (RetrievedChunk childChunk : childChunks) {
                    deduped.putIfAbsent(childChunk.chunk().chunkId(), childChunk);
                }
                continue;
            }

            double meanScore = childChunks.stream()
                .mapToDouble(RetrievedChunk::score)
                .average()
                .orElse(0.0d);
            RetrievedChunk aggregatedParent = new RetrievedChunk(
                parent,
                meanScore,
                "ragflow_children_aggregate",
                "Aggregated child chunks into parent chunk using mom_id."
            );
            RetrievedChunk existing = deduped.get(parent.chunkId());
            if (existing == null || aggregatedParent.score() >= existing.score()) {
                deduped.put(parent.chunkId(), aggregatedParent);
            }
        }

        return deduped.values().stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .toList();
    }

    private IndexedChunk lookupParentChunk(String parentChunkId, RetrievedChunk childChunk) {
        return knowledgeStore.listChunks(childChunk.chunk().collectionId()).stream()
            .filter(chunk -> parentChunkId.equals(chunk.chunkId()))
            .findFirst()
            .orElse(null);
    }

    private String parentChunkId(RetrievedChunk chunk) {
        Object value = chunk.chunk().metadata().get("mom_id");
        if (value == null) {
            return null;
        }
        String parentChunkId = String.valueOf(value).trim();
        return parentChunkId.isBlank() ? null : parentChunkId;
    }
}

package com.realityrag.retrieval.contracts;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record KnowledgeContext(
    String queryId,
    Map<String, Object> principalContext,
    List<String> indexVersionUsed,
    List<CollectionRetrievalPlan> collectionPlansUsed,
    @JsonProperty("evidence_items") List<ResultChunk> resultChunks,
    List<Map<String, Object>> groupedSources,
    List<Map<String, Object>> citations,
    int tokenBudgetUsed,
    Map<String, Object> retrievalDebug
) {
    public KnowledgeContext {
        principalContext = principalContext == null ? Map.of() : Map.copyOf(principalContext);
        indexVersionUsed = indexVersionUsed == null ? List.of() : List.copyOf(indexVersionUsed);
        collectionPlansUsed = collectionPlansUsed == null ? List.of() : List.copyOf(collectionPlansUsed);
        resultChunks = resultChunks == null ? List.of() : List.copyOf(resultChunks);
        groupedSources = groupedSources == null ? List.of() : List.copyOf(groupedSources);
        citations = citations == null ? List.of() : List.copyOf(citations);
        retrievalDebug = retrievalDebug == null ? Map.of() : Map.copyOf(retrievalDebug);
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record ResultChunk(
        String collectionId,
        @JsonProperty("doc_id") String finalDocId,
        @JsonProperty("evidence_id") String chunkId,
        String documentIndexRevisionId,
        @JsonProperty("content") String displayText,
        List<String> sectionPath,
        List<PageSpan> pageSpans,
        double score,
        String sourceStage,
        String whySelected
    ) {
        public ResultChunk {
            sectionPath = sectionPath == null ? List.of() : List.copyOf(sectionPath);
            pageSpans = pageSpans == null ? List.of() : List.copyOf(pageSpans);
        }
    }

    public record PageSpan(int pageFrom, int pageTo) {}
}

package com.realityrag.access.contracts;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record KnowledgeContext(
    @JsonProperty("query_id") String queryId,
    @JsonProperty("principal_context") Map<String, Object> principalContext,
    @JsonProperty("index_version_used") List<String> indexVersionUsed,
    @JsonProperty("collection_plans_used") List<Map<String, Object>> collectionPlansUsed,
    @JsonProperty("evidence_items") List<ResultChunk> resultChunks,
    @JsonProperty("grouped_sources") List<Map<String, Object>> groupedSources,
    @JsonProperty("citations") List<Map<String, Object>> citations,
    @JsonProperty("token_budget_used") int tokenBudgetUsed,
    @JsonProperty("retrieval_debug") Map<String, Object> retrievalDebug
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

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record PageSpan(int pageFrom, int pageTo) {}
}

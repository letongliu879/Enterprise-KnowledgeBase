package com.realityrag.retrieval.contracts;

import java.time.Instant;
import java.util.Map;

public record RetrievalProfile(
    String profileId,
    String collectionId,
    int profileVersion,
    String profileHash,
    double bm25Weight,
    double vectorWeight,
    int candidateTopK,
    double similarityThreshold,
    boolean rerankEnabled,
    String rerankModel,
    String failPolicy,
    Map<String, Object> expansionPolicy,
    int packBudget,
    Instant updatedAt,
    String updatedBy
) {
    public RetrievalProfile {
        expansionPolicy = expansionPolicy == null ? Map.of() : Map.copyOf(expansionPolicy);
    }
}

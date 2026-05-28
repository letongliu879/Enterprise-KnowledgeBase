package com.realityrag.retrieval.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record RetrievalProfileProjectionSyncRequest(
    @NotBlank String commandId,
    @NotBlank String traceId,
    @NotBlank String idempotencyKey,
    @NotBlank String actor,
    @NotBlank String tenantId,
    @NotBlank String targetType,
    @NotBlank String targetId,
    @NotNull @Valid RetrievalProfileProjection payload
) {
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record RetrievalProfileProjection(
        @NotBlank String profileId,
        String collectionId,
        int profileVersion,
        @NotBlank String profileHash,
        double bm25Weight,
        double vectorWeight,
        int candidateTopK,
        double similarityThreshold,
        boolean rerankEnabled,
        @NotBlank String rerankModel,
        @NotBlank String failPolicy,
        Map<String, Object> expansionPolicy,
        int packBudget,
        boolean enabled,
        String updatedAt,
        @NotBlank String updatedBy
    ) {
        public RetrievalProfileProjection {
            expansionPolicy = expansionPolicy == null ? Map.of() : Map.copyOf(expansionPolicy);
        }
    }
}

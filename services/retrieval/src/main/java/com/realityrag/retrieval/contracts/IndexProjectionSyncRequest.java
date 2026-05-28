package com.realityrag.retrieval.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.util.List;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record IndexProjectionSyncRequest(
    @NotBlank String commandId,
    @NotBlank String traceId,
    @NotBlank String idempotencyKey,
    @NotBlank String actor,
    @NotBlank String tenantId,
    @NotBlank String targetType,
    @NotBlank String targetId,
    @NotNull @Valid IndexProjectionPayload payload
) {
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record IndexProjectionPayload(
        @NotBlank String collectionId,
        @NotBlank String indexVersionId,
        @NotBlank String syncMode,
        String docId,
        String lifecycleState,
        Integer availableInt,
        List<Map<String, Object>> chunks,
        String tenantId,
        String opensearchIndex,
        String qdrantCollection,
        String embeddingModel,
        String chunkProfileId,
        String indexProfileId,
        String schemaVersion,
        String publishedDocumentState
    ) {
    }
}

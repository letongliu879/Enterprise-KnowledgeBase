package com.realityrag.retrieval.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record IndexProjectionSyncResponse(
    String syncedAt,
    int chunksSynced,
    int chunksRemoved
) {
}

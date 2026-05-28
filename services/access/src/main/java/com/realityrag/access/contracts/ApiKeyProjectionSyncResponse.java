package com.realityrag.access.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.time.Instant;

/**
 * Response from POST /internal/api-key-projections/sync.
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ApiKeyProjectionSyncResponse(
    Instant syncedAt,
    boolean runtimeSynced
) {}

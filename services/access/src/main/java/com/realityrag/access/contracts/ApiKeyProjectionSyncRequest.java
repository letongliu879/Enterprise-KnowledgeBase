package com.realityrag.access.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * Command envelope for syncing an API key projection to access runtime.
 *
 * <p>All mutation commands MUST carry a stable idempotency_key.
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ApiKeyProjectionSyncRequest(
    @NotBlank String commandId,
    @NotBlank String traceId,
    @NotBlank String idempotencyKey,
    @NotBlank String actor,
    @NotBlank String tenantId,
    @NotBlank String targetType,
    @NotBlank String targetId,
    @NotNull @Valid ApiKeyProjection payload
) {}

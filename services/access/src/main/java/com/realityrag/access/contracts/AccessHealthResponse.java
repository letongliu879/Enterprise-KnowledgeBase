package com.realityrag.access.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record AccessHealthResponse(
    String service,
    String status,
    String retrievalStatus
) {}

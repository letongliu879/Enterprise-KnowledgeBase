package com.realityrag.retrieval.contracts;

import jakarta.validation.constraints.NotBlank;

public record CachePurgeRequest(
    @NotBlank String tenantId,
    String collectionId,
    String docId,
    String evidenceId
) {
}

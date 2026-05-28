package com.realityrag.retrieval.scope.sources;

public record IndexRegistryRecord(
    String tenantId,
    String collectionId,
    String indexVersionId,
    String opensearchIndex,
    String qdrantCollection,
    String embeddingModel,
    String chunkProfileId
) {}

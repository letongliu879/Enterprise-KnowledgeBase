package com.realityrag.retrieval.contracts;

import java.util.List;
import java.util.Map;

public record CollectionRetrievalPlan(
    String collectionId,
    String activeIndexVersionId,
    String opensearchIndex,
    String qdrantCollection,
    String embeddingModel,
    String chunkProfileId,
    Map<String, Object> retrievalProfileSnapshot,
    String profileId,
    int profileVersion,
    String profileHash,
    Map<String, Object> permissionScope,
    Map<String, Object> lifecycleFilter,
    boolean includeDeprecated,
    List<String> allowedDocIds,
    Map<String, Object> metadataFilters
) {
    public CollectionRetrievalPlan {
        retrievalProfileSnapshot = retrievalProfileSnapshot == null ? Map.of() : Map.copyOf(retrievalProfileSnapshot);
        permissionScope = permissionScope == null ? Map.of() : Map.copyOf(permissionScope);
        lifecycleFilter = lifecycleFilter == null ? Map.of() : Map.copyOf(lifecycleFilter);
        allowedDocIds = allowedDocIds == null ? List.of() : List.copyOf(allowedDocIds);
        metadataFilters = metadataFilters == null ? Map.of() : Map.copyOf(metadataFilters);
    }
}

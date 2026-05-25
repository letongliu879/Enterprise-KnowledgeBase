package com.realityrag.retrieval.contracts;

import java.util.List;
import java.util.Map;

public record RetrievalScope(
    String principalId,
    List<String> collectionIds,
    List<String> allowedDocIds,
    Map<String, Object> metadataFilters,
    boolean includeDeprecated,
    String permissionFingerprint,
    List<CollectionRetrievalPlan> collectionPlans
) {
    public RetrievalScope {
        collectionIds = collectionIds == null ? List.of() : List.copyOf(collectionIds);
        allowedDocIds = allowedDocIds == null ? List.of() : List.copyOf(allowedDocIds);
        metadataFilters = metadataFilters == null ? Map.of() : Map.copyOf(metadataFilters);
        collectionPlans = collectionPlans == null ? List.of() : List.copyOf(collectionPlans);
    }
}

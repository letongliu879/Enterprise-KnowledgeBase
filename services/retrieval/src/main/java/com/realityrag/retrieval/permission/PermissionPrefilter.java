package com.realityrag.retrieval.permission;

import com.realityrag.retrieval.contracts.RetrievalScope;
import com.realityrag.retrieval.store.IndexedChunk;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class PermissionPrefilter {
    public List<IndexedChunk> filter(RetrievalScope scope, List<IndexedChunk> chunks) {
        @SuppressWarnings("unchecked")
        List<String> allowedStates = (List<String>) scope.metadataFilters()
            .getOrDefault("allowed_states", List.of("PUBLISHED"));
        return chunks.stream()
            .filter(chunk -> scope.collectionIds().contains(chunk.collectionId()))
            .filter(chunk -> allowedStates.contains(chunk.publishedDocumentState()))
            .filter(chunk -> scope.allowedDocIds().contains(chunk.finalDocId()))
            .filter(chunk -> hasPrincipalAccess(scope, chunk))
            .filter(chunk -> matchesMetadataFilters(scope.metadataFilters(), chunk))
            .toList();
    }

    private boolean hasPrincipalAccess(RetrievalScope scope, IndexedChunk chunk) {
        if (chunk.allowedPrincipalIds().isEmpty() && chunk.allowedGroups().isEmpty()) {
            return true;
        }
        if (chunk.allowedPrincipalIds().contains(scope.principalId())) {
            return true;
        }
        @SuppressWarnings("unchecked")
        List<String> principalGroups = (List<String>) scope.metadataFilters().getOrDefault("principal_groups", List.of());
        return principalGroups.stream().anyMatch(chunk.allowedGroups()::contains);
    }

    private boolean matchesMetadataFilters(Map<String, Object> metadataFilters, IndexedChunk chunk) {
        Object visibilityFilter = metadataFilters.get("visibility");
        return visibilityFilter == null || visibilityFilter.equals(chunk.visibility());
    }
}

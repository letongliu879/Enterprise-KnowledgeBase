package com.realityrag.retrieval.scope.sources;

import java.util.List;

public record PublishedDocumentRecord(
    String collectionId,
    String finalDocId,
    String publishedDocumentState,
    String activeIndexVersionId,
    String visibility,
    List<String> allowedPrincipalIds,
    List<String> allowedGroups
) {
    public PublishedDocumentRecord {
        allowedPrincipalIds = allowedPrincipalIds == null ? List.of() : List.copyOf(allowedPrincipalIds);
        allowedGroups = allowedGroups == null ? List.of() : List.copyOf(allowedGroups);
    }
}

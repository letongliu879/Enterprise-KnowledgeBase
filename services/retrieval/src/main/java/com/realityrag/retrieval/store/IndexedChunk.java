package com.realityrag.retrieval.store;

import com.realityrag.retrieval.contracts.KnowledgeContext;
import java.util.List;
import java.util.Map;

public record IndexedChunk(
    String collectionId,
    String finalDocId,
    String indexVersionId,
    String documentIndexRevisionId,
    String chunkId,
    String displayText,
    String vectorText,
    List<String> sectionPath,
    List<KnowledgeContext.PageSpan> pageSpans,
    String publishedDocumentState,
    String visibility,
    List<String> allowedPrincipalIds,
    List<String> allowedGroups,
    Map<String, Object> citationPayload,
    Map<String, Object> metadata
) {
    public IndexedChunk {
        sectionPath = sectionPath == null ? List.of() : List.copyOf(sectionPath);
        pageSpans = pageSpans == null ? List.of() : List.copyOf(pageSpans);
        allowedPrincipalIds = allowedPrincipalIds == null ? List.of() : List.copyOf(allowedPrincipalIds);
        allowedGroups = allowedGroups == null ? List.of() : List.copyOf(allowedGroups);
        citationPayload = citationPayload == null ? Map.of() : Map.copyOf(citationPayload);
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    }
}

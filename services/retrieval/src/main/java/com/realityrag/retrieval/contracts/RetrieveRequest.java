package com.realityrag.retrieval.contracts;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Positive;
import java.util.List;
import java.util.Map;

public record RetrieveRequest(
    @NotBlank String queryId,
    @NotBlank String traceId,
    @Valid PrincipalRef principal,
    @NotEmpty List<String> collectionScope,
    @NotBlank String queryText,
    String language,
    List<String> crossLanguages,
    Boolean keyword,
    Map<String, Object> metaDataFilter,
    @NotBlank String retrievalProfileId,
    Map<String, Object> filters,
    boolean includeDeprecated,
    @Positive Integer maxContextTokens,
    @NotBlank String debugLevel
) {
    public RetrieveRequest {
        collectionScope = collectionScope == null ? List.of() : List.copyOf(collectionScope);
        crossLanguages = crossLanguages == null ? List.of() : List.copyOf(crossLanguages);
        keyword = keyword == null ? Boolean.FALSE : keyword;
        metaDataFilter = metaDataFilter == null ? Map.of() : Map.copyOf(metaDataFilter);
        filters = filters == null ? Map.of() : Map.copyOf(filters);
        debugLevel = debugLevel == null || debugLevel.isBlank() ? "none" : debugLevel;
    }
}

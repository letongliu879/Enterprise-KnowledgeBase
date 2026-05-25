package com.realityrag.access.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record InternalRetrieveRequest(
    String queryId,
    String traceId,
    InternalPrincipal principal,
    List<String> collectionScope,
    String queryText,
    String language,
    List<String> crossLanguages,
    Boolean keyword,
    Map<String, Object> metaDataFilter,
    String retrievalProfileId,
    Map<String, Object> filters,
    boolean includeDeprecated,
    Integer maxContextTokens,
    String debugLevel
) {
    public InternalRetrieveRequest {
        collectionScope = collectionScope == null ? List.of() : List.copyOf(collectionScope);
        crossLanguages = crossLanguages == null ? List.of() : List.copyOf(crossLanguages);
        keyword = keyword == null ? Boolean.FALSE : keyword;
        metaDataFilter = metaDataFilter == null ? Map.of() : Map.copyOf(metaDataFilter);
        filters = filters == null ? Map.of() : Map.copyOf(filters);
    }
}

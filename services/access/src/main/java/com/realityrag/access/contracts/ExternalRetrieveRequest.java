package com.realityrag.access.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import java.util.List;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ExternalRetrieveRequest(
    @NotBlank String query,
    @NotEmpty List<@NotBlank String> collectionScope,
    Map<String, Object> filters,
    String language,
    List<String> crossLanguages,
    Boolean keyword,
    Map<String, Object> metaDataFilter,
    String retrievalProfileId,
    String profile,
    @Positive Integer maxContextTokens,
    @Pattern(regexp = "none|basic|full", message = "debug must be one of: none, basic, full")
    String debug
) {
    public ExternalRetrieveRequest {
        collectionScope = collectionScope == null ? List.of() : List.copyOf(collectionScope);
        filters = filters == null ? Map.of() : Map.copyOf(filters);
        crossLanguages = crossLanguages == null ? List.of() : List.copyOf(crossLanguages);
        metaDataFilter = metaDataFilter == null ? Map.of() : Map.copyOf(metaDataFilter);
    }
}

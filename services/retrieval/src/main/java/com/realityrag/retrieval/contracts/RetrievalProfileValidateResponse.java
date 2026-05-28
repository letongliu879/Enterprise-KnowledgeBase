package com.realityrag.retrieval.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record RetrievalProfileValidateResponse(
    boolean valid,
    Map<String, Object> canonicalConfig,
    String profileHash,
    List<String> warnings,
    List<ValidationError> errors,
    String runtimeOwner,
    String validatorVersion
) {
    public RetrievalProfileValidateResponse {
        // Allow canonicalConfig to remain null when valid=false so Jackson non_null omits it
        warnings = warnings == null ? List.of() : List.copyOf(warnings);
        errors = errors == null ? List.of() : List.copyOf(errors);
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record ValidationError(String code, String message) {}
}

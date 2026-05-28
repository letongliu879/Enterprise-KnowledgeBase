package com.realityrag.retrieval.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record RetrievalProfileValidateRequest(
    @NotBlank String retrievalProfileId,
    @NotNull Map<String, Object> profileConfig,
    @NotBlank String tenantId,
    String collectionId,
    String version
) {
    public RetrievalProfileValidateRequest {
        profileConfig = profileConfig == null ? Map.of() : Map.copyOf(profileConfig);
    }
}

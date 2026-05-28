package com.realityrag.retrieval.contracts;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import java.util.List;
import java.util.Map;

public record PrincipalRef(
    @NotBlank @JsonProperty("user_id") String principalId,
    @JsonProperty("role_ids") List<String> roles,
    @JsonProperty("group_ids") List<String> groups,
    Map<String, Object> attributes
) {
    public PrincipalRef {
        roles = roles == null ? List.of() : List.copyOf(roles);
        groups = groups == null ? List.of() : List.copyOf(groups);
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }
}

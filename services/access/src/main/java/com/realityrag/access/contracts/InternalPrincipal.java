package com.realityrag.access.contracts;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;
import java.util.Map;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record InternalPrincipal(
    String principalId,
    List<String> roles,
    List<String> groups,
    Map<String, Object> attributes
) {
    public InternalPrincipal {
        roles = roles == null ? List.of() : List.copyOf(roles);
        groups = groups == null ? List.of() : List.copyOf(groups);
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }
}

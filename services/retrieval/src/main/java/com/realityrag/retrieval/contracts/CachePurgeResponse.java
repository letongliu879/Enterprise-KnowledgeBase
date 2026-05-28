package com.realityrag.retrieval.contracts;

import java.util.Map;

public record CachePurgeResponse(
    long purgedCount,
    Map<String, Object> scope
) {
}

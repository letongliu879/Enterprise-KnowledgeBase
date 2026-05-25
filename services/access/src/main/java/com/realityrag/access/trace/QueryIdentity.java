package com.realityrag.access.trace;

public record QueryIdentity(
    String queryId,
    String traceId
) {}

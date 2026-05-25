package com.realityrag.access.trace;

import com.realityrag.access.contracts.InternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.security.AccessRequestContext;
public class NoOpAccessTraceRecorder implements AccessTraceRecorder {
    @Override
    public void recordRequestAccepted(String queryId, String traceId, AccessRequestContext context) {}

    @Override
    public void recordRateLimitChecked(String queryId, String traceId, AccessRequestContext context) {}

    @Override
    public void recordRetrievalCall(InternalRetrieveRequest request) {}

    @Override
    public void recordResponse(String queryId, String traceId, KnowledgeContext response) {}

    @Override
    public void recordFailure(String queryId, String traceId, AccessRequestContext context, Exception error) {}
}

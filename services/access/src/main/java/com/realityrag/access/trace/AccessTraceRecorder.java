package com.realityrag.access.trace;

import com.realityrag.access.contracts.InternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.security.AccessRequestContext;

public interface AccessTraceRecorder {
    void recordRequestAccepted(String queryId, String traceId, AccessRequestContext context);

    void recordRateLimitChecked(String queryId, String traceId, AccessRequestContext context);

    void recordRetrievalCall(InternalRetrieveRequest request);

    void recordResponse(String queryId, String traceId, KnowledgeContext response);

    void recordFailure(String queryId, String traceId, AccessRequestContext context, Exception error);
}

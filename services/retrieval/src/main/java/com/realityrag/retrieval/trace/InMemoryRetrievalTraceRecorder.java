package com.realityrag.retrieval.trace;

import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.recall.RetrievedChunk;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class InMemoryRetrievalTraceRecorder implements RetrievalTraceRecorder {
    private static final Logger log = LoggerFactory.getLogger(InMemoryRetrievalTraceRecorder.class);
    private final Map<String, Object> traces = new ConcurrentHashMap<>();

    @Override
    public String record(RetrieveRequest request, List<CollectionRetrievalPlan> plans, List<RetrievedChunk> chunks) {
        String debugRef = "dbg://retrieval/" + request.queryId();
        log.info(
            "RETRIEVAL_AUDIT event=response query_id={} trace_id={} principal_id={} collection_scope={} retrieval_profile_id={} plan_count={} result_count={} token_budget_used={} debug_level={}",
            request.queryId(),
            request.traceId(),
            request.principal() == null ? "unknown" : request.principal().principalId(),
            request.collectionScope(),
            request.retrievalProfileId(),
            plans.size(),
            chunks.size(),
            request.maxContextTokens(),
            request.debugLevel()
        );
        traces.put(
            debugRef,
            Map.of(
                "trace_id", request.traceId(),
                "query_id", request.queryId(),
                "plan_count", plans.size(),
                "result_count", chunks.size()
            )
        );
        return debugRef;
    }

    @Override
    public void recordFailure(RetrieveRequest request, List<CollectionRetrievalPlan> plans, Exception error) {
        log.warn(
            "RETRIEVAL_AUDIT event=failure query_id={} trace_id={} principal_id={} collection_scope={} retrieval_profile_id={} plan_count={} error_type={} error_message={}",
            request.queryId(),
            request.traceId(),
            request.principal() == null ? "unknown" : request.principal().principalId(),
            request.collectionScope(),
            request.retrievalProfileId(),
            plans == null ? 0 : plans.size(),
            error.getClass().getSimpleName(),
            error.getMessage()
        );
    }
}

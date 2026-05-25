package com.realityrag.access.trace;

import com.realityrag.access.contracts.InternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.security.AccessRequestContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class LoggingAccessTraceRecorder implements AccessTraceRecorder {
    private static final Logger log = LoggerFactory.getLogger(LoggingAccessTraceRecorder.class);

    @Override
    public void recordRequestAccepted(String queryId, String traceId, AccessRequestContext context) {
        log.info(
            "ACCESS_AUDIT event=request_accepted query_id={} trace_id={} api_key_id={} agent_type_id={} agent_instance_id={} client_type={} knowledge_scopes={} max_context_tokens={}",
            queryId,
            traceId,
            context.apiKeyId(),
            context.agentTypeId(),
            context.agentInstanceId(),
            context.clientType(),
            context.knowledgeScopes(),
            context.maxContextTokens()
        );
    }

    @Override
    public void recordRateLimitChecked(String queryId, String traceId, AccessRequestContext context) {
        log.info(
            "ACCESS_AUDIT event=rate_limit_checked query_id={} trace_id={} agent_instance_id={} client_type={}",
            queryId,
            traceId,
            context.agentInstanceId(),
            context.clientType()
        );
    }

    @Override
    public void recordRetrievalCall(InternalRetrieveRequest request) {
        log.info(
            "ACCESS_AUDIT event=retrieval_call query_id={} trace_id={} principal_id={} collection_scope={} retrieval_profile_id={} debug_level={} max_context_tokens={} query_chars={}",
            request.queryId(),
            request.traceId(),
            request.principal() == null ? "unknown" : request.principal().principalId(),
            request.collectionScope(),
            request.retrievalProfileId(),
            request.debugLevel(),
            request.maxContextTokens(),
            request.queryText() == null ? 0 : request.queryText().length()
        );
    }

    @Override
    public void recordResponse(String queryId, String traceId, KnowledgeContext response) {
        log.info(
            "ACCESS_AUDIT event=response query_id={} trace_id={} result_count={} citation_count={} token_budget_used={} debug_ref={} index_versions={}",
            queryId,
            traceId,
            response.resultChunks().size(),
            response.citations().size(),
            response.tokenBudgetUsed(),
            response.retrievalDebug().getOrDefault("debug_ref", "none"),
            response.indexVersionUsed()
        );
    }

    @Override
    public void recordFailure(String queryId, String traceId, AccessRequestContext context, Exception error) {
        log.warn(
            "ACCESS_AUDIT event=failure query_id={} trace_id={} api_key_id={} agent_type_id={} agent_instance_id={} client_type={} error_type={} error_message={}",
            queryId,
            traceId,
            context.apiKeyId(),
            context.agentTypeId(),
            context.agentInstanceId(),
            context.clientType(),
            error.getClass().getSimpleName(),
            error.getMessage()
        );
    }
}

package com.realityrag.access.trace;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.contracts.InternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.security.AccessRequestContext;
import io.micrometer.core.instrument.MeterRegistry;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.TransientDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class LoggingAccessTraceRecorder {
    private static final Logger log = LoggerFactory.getLogger(LoggingAccessTraceRecorder.class);
    private static final int MAX_RETRIES = 3;
    private static final long[] RETRY_BACKOFF_MS = {50L, 200L, 1_000L};

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;
    private final MeterRegistry meterRegistry;
    private final AtomicLong droppedCount = new AtomicLong(0L);

    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "access-audit-writer");
        t.setDaemon(true);
        return t;
    });

    public LoggingAccessTraceRecorder(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper, MeterRegistry meterRegistry) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.meterRegistry = meterRegistry;
    }

    @PostConstruct
    void validateSchema() {
        if (!_tableExists("run_traces") || !_tableExists("run_steps")) {
            throw new IllegalStateException(
                "Required audit tables are missing. Run 'uv run alembic -c packages/persistence/migrations/alembic.ini upgrade head' before starting the access service."
            );
        }
    }

    private boolean _tableExists(String tableName) {
        try {
            jdbcTemplate.queryForObject(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1",
                Integer.class,
                tableName
            );
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @PreDestroy
    void shutdown() {
        executor.shutdown();
        try { executor.awaitTermination(5, TimeUnit.SECONDS); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }

    void flush() {
        try {
            executor.submit(() -> {}).get(5, TimeUnit.SECONDS);
        } catch (Exception e) {
            Thread.currentThread().interrupt();
        }
    }

    public void recordRequestAccepted(String queryId, String traceId, AccessRequestContext context) {
        Map<String, Object> details = contextDetails(queryId, traceId, context);
        executor.submit(() -> executeWithRetry(() -> {
            upsertTrace(queryId, traceId, context, "ACCEPTED", "dbg://access/" + queryId, 0, details);
            insertStep(traceId, "access.request_accepted", "SUCCEEDED", "api_key_id=" + context.apiKeyId(), details);
        }));
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

    public void recordRetrievalCall(InternalRetrieveRequest request) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("query_id", request.queryId());
        details.put("trace_id", request.traceId());
        details.put("principal_id", request.principal() == null ? "" : request.principal().principalId());
        details.put("collection_scope", request.collectionScope());
        details.put("retrieval_profile_id", request.retrievalProfileId());
        details.put("debug_level", request.debugLevel());
        details.put("max_context_tokens", request.maxContextTokens());
        details.put("query_chars", request.queryText() == null ? 0 : request.queryText().length());
        Map<String, Object> detailsFinal = details;
        executor.submit(() -> executeWithRetry(() -> {
            insertStep(request.traceId(), "access.retrieval_call", "SUCCEEDED", "collections=" + request.collectionScope(), detailsFinal);
        }));
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

    public void recordResponse(String queryId, String traceId, KnowledgeContext response) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("query_id", queryId);
        details.put("trace_id", traceId);
        details.put("result_count", response.resultChunks().size());
        details.put("citation_count", response.citations().size());
        details.put("index_versions", response.indexVersionUsed());
        details.put("chunk_ids", response.resultChunks().stream().map(KnowledgeContext.ResultChunk::chunkId).toList());
        details.put("final_doc_ids", response.resultChunks().stream().map(KnowledgeContext.ResultChunk::finalDocId).distinct().toList());
        details.put("debug_ref", response.retrievalDebug().getOrDefault("debug_ref", "none"));
        String debugRef = String.valueOf(response.retrievalDebug().getOrDefault("debug_ref", "dbg://access/" + queryId));
        int resultCount = response.resultChunks().size();
        executor.submit(() -> executeWithRetry(() -> {
            updateTrace(queryId, "SUCCEEDED", debugRef, resultCount, details);
            insertStep(traceId, "access.response", "SUCCEEDED", "result_count=" + resultCount, details);
        }));
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

    public void recordFailure(String queryId, String traceId, AccessRequestContext context, Exception error) {
        Map<String, Object> details = contextDetails(queryId, traceId, context);
        details.put("error_type", error.getClass().getSimpleName());
        details.put("error_message", error.getMessage());
        executor.submit(() -> executeWithRetry(() -> {
            upsertTrace(queryId, traceId, context, "FAILED", "dbg://access/" + queryId, 0, details);
            insertStep(traceId, "access.failure", "FAILED", error.getMessage(), details);
        }));
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

    private void upsertTrace(
        String queryId,
        String traceId,
        AccessRequestContext context,
        String status,
        String debugRef,
        int resultCount,
        Map<String, Object> details
    ) {
        String runTraceId = "access_" + queryId;
        int updated = jdbcTemplate.update(
            """
                UPDATE run_traces
                SET root_status = ?, debug_ref = ?, result_count = ?, extra_json = ?::json, updated_at = CURRENT_TIMESTAMP
                WHERE run_trace_id = ?
                """,
            status,
            debugRef,
            resultCount,
            json(details),
            runTraceId
        );
        if (updated == 0) {
            jdbcTemplate.update(
                """
                    INSERT INTO run_traces (
                        run_trace_id, trace_id, run_kind, tenant_id, collection_id, principal_id,
                        query_id, index_version_id, profile_id, root_status, debug_ref, result_count,
                        extra_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::json, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                runTraceId,
                traceId,
                "access",
                "",
                String.join(",", context.knowledgeScopes()),
                context.apiKeyId() + "/" + context.agentInstanceId(),
                queryId,
                "",
                "",
                status,
                debugRef,
                resultCount,
                json(details)
            );
        }
    }

    private void updateTrace(String queryId, String status, String debugRef, int resultCount, Map<String, Object> details) {
        jdbcTemplate.update(
            """
                UPDATE run_traces
                SET root_status = ?, debug_ref = ?, result_count = ?, extra_json = ?::json, updated_at = CURRENT_TIMESTAMP
                WHERE run_trace_id = ?
                """,
            status,
            debugRef,
            resultCount,
            json(details),
            "access_" + queryId
        );
    }

    private void insertStep(String traceId, String stepName, String status, String summary, Map<String, Object> details) {
        jdbcTemplate.update(
            """
                INSERT INTO run_steps (trace_id, step_name, status, summary, details_json, created_at)
                VALUES (?, ?, ?, ?, ?::json, CURRENT_TIMESTAMP)
                """,
            traceId,
            stepName,
            status,
            summary == null ? "" : summary,
            json(details)
        );
    }

    private Map<String, Object> contextDetails(String queryId, String traceId, AccessRequestContext context) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("query_id", queryId);
        details.put("trace_id", traceId);
        details.put("api_key_id", context.apiKeyId());
        details.put("agent_type_id", context.agentTypeId());
        details.put("agent_instance_id", context.agentInstanceId());
        details.put("client_type", context.clientType());
        details.put("knowledge_scopes", context.knowledgeScopes());
        details.put("roles", context.roles());
        details.put("max_context_tokens", context.maxContextTokens());
        return details;
    }

    private String json(Map<String, Object> details) {
        try {
            return objectMapper.writeValueAsString(details);
        }
        catch (Exception error) {
            throw new IllegalStateException("Failed to serialize access audit details", error);
        }
    }

    private void executeWithRetry(Runnable action) {
        for (int attempt = 0; attempt <= MAX_RETRIES; attempt++) {
            try {
                action.run();
                return;
            } catch (TransientDataAccessException e) {
                if (attempt == MAX_RETRIES) {
                    long total = droppedCount.incrementAndGet();
                    meterRegistry.counter("access.audit.dropped").increment();
                    log.warn("ACCESS_AUDIT trace recording skipped after {} retries (total dropped: {}): {}",
                        MAX_RETRIES, total, e.getMessage());
                    return;
                }
                try {
                    Thread.sleep(RETRY_BACKOFF_MS[attempt]);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    long total = droppedCount.incrementAndGet();
                    meterRegistry.counter("access.audit.dropped").increment();
                    log.warn("ACCESS_AUDIT retry interrupted (total dropped: {})", total);
                    return;
                }
            }
        }
    }

    long droppedCount() {
        return droppedCount.get();
    }
}

package com.realityrag.retrieval.trace;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.recall.RetrievedChunk;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class JdbcRetrievalTraceRecorder implements RetrievalTraceRecorder {
    private static final Logger log = LoggerFactory.getLogger(JdbcRetrievalTraceRecorder.class);

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public JdbcRetrievalTraceRecorder(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @Override
    public String record(RetrieveRequest request, List<CollectionRetrievalPlan> plans, List<RetrievedChunk> chunks) {
        String debugRef = "dbg://retrieval/" + request.queryId();
        Map<String, Object> details = baseDetails(request, plans);
        details.put("result_count", chunks.size());
        details.put("chunk_ids", chunks.stream().map(chunk -> chunk.chunk().chunkId()).toList());
        details.put("final_doc_ids", chunks.stream().map(chunk -> chunk.chunk().finalDocId()).distinct().toList());
        details.put("source_stages", chunks.stream().map(RetrievedChunk::sourceStage).distinct().toList());
        upsertTrace(request, plans, "SUCCEEDED", debugRef, chunks.size(), details);
        insertStep(request.traceId(), "retrieval.response", "SUCCEEDED", summary(request, plans, chunks.size()), details);
        log.info(
            "RETRIEVAL_AUDIT event=response query_id={} trace_id={} principal_id={} collection_scope={} index_versions={} result_count={}",
            request.queryId(),
            request.traceId(),
            request.principal() == null ? "unknown" : request.principal().principalId(),
            request.collectionScope(),
            plans.stream().map(CollectionRetrievalPlan::activeIndexVersionId).toList(),
            chunks.size()
        );
        return debugRef;
    }

    @Override
    public void recordFailure(RetrieveRequest request, List<CollectionRetrievalPlan> plans, Exception error) {
        Map<String, Object> details = baseDetails(request, plans == null ? List.of() : plans);
        details.put("error_type", error.getClass().getSimpleName());
        details.put("error_message", error.getMessage());
        upsertTrace(request, plans == null ? List.of() : plans, "FAILED", "dbg://retrieval/" + request.queryId(), 0, details);
        insertStep(request.traceId(), "retrieval.failure", "FAILED", error.getMessage(), details);
        log.warn(
            "RETRIEVAL_AUDIT event=failure query_id={} trace_id={} principal_id={} collection_scope={} error_type={} error_message={}",
            request.queryId(),
            request.traceId(),
            request.principal() == null ? "unknown" : request.principal().principalId(),
            request.collectionScope(),
            error.getClass().getSimpleName(),
            error.getMessage()
        );
    }

    private void upsertTrace(
        RetrieveRequest request,
        List<CollectionRetrievalPlan> plans,
        String status,
        String debugRef,
        int resultCount,
        Map<String, Object> details
    ) {
        String runTraceId = "retrieval_" + request.queryId();
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
                request.traceId(),
                "retrieval",
                "",
                plans.stream().map(CollectionRetrievalPlan::collectionId).findFirst().orElse(""),
                request.principal() == null ? "" : request.principal().principalId(),
                request.queryId(),
                plans.stream().map(CollectionRetrievalPlan::activeIndexVersionId).findFirst().orElse(""),
                request.retrievalProfileId(),
                status,
                debugRef,
                resultCount,
                json(details)
            );
        }
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

    private Map<String, Object> baseDetails(RetrieveRequest request, List<CollectionRetrievalPlan> plans) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("query_id", request.queryId());
        details.put("trace_id", request.traceId());
        details.put("principal_id", request.principal() == null ? "" : request.principal().principalId());
        details.put("collection_scope", request.collectionScope());
        details.put("retrieval_profile_id", request.retrievalProfileId());
        details.put("debug_level", request.debugLevel());
        details.put("plan_count", plans.size());
        details.put("index_versions", plans.stream().map(CollectionRetrievalPlan::activeIndexVersionId).toList());
        details.put("allowed_doc_ids", plans.stream().flatMap(plan -> plan.allowedDocIds().stream()).distinct().toList());
        return details;
    }

    private String summary(RetrieveRequest request, List<CollectionRetrievalPlan> plans, int resultCount) {
        return "query_id=" + request.queryId()
            + ";collections=" + request.collectionScope()
            + ";index_versions=" + plans.stream().map(CollectionRetrievalPlan::activeIndexVersionId).toList()
            + ";result_count=" + resultCount;
    }

    private String json(Map<String, Object> details) {
        try {
            return objectMapper.writeValueAsString(details);
        }
        catch (Exception error) {
            throw new IllegalStateException("Failed to serialize retrieval audit details", error);
        }
    }
}

package com.realityrag.retrieval.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * Real wire-format tests that verify the retrieval-service contracts produce
 * the correct canonical wire names.
 *
 * Canonical wire:
 * - query (not query_text)
 * - token_budget (not max_context_tokens)
 * - evidence_items (not result_chunks)
 * - doc_id (not final_doc_id)
 * - evidence_id (not chunk_id)
 * - content (not display_text)
 */
class RetrievalWireTest {

    private final ObjectMapper objectMapper = new ObjectMapper()
        .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);

    @Test
    void retrieveRequestUsesCanonicalWireNames() throws Exception {
        RetrieveRequest request = new RetrieveRequest(
            "qry_001",
            "trc_001",
            new PrincipalRef(
                "usr_001",
                List.of("employee"),
                List.of("finance"),
                Map.of("region", "apac")
            ),
            List.of("col_policy"),
            "What expenses are reimbursable?",
            "en",
            List.of("zh"),
            false,
            Map.of("mode", "manual"),
            "ret_default",
            Map.of("visibility", "internal"),
            false,
            1200,
            "basic"
        );

        String json = objectMapper.writeValueAsString(request);
        JsonNode tree = objectMapper.readTree(json);

        // Verify canonical names
        assertEquals("What expenses are reimbursable?", tree.get("query").asText(),
            "Wire must use 'query'");
        assertEquals(1200, tree.get("token_budget").asInt(),
            "Wire must use 'token_budget'");
        assertEquals("qry_001", tree.get("query_id").asText());
        assertEquals("trc_001", tree.get("trace_id").asText());

        // Verify old names are absent
        assertTrue(tree.get("query_text") == null,
            "Wire must NOT contain 'query_text'");
        assertTrue(tree.get("max_context_tokens") == null,
            "Wire must NOT contain 'max_context_tokens'");
        assertFalse(json.contains("\"query_text\""),
            "Raw JSON must not contain 'query_text'");
        assertFalse(json.contains("\"max_context_tokens\""),
            "Raw JSON must not contain 'max_context_tokens'");
    }

    @Test
    void knowledgeContextUsesCanonicalWireNames() throws Exception {
        KnowledgeContext context = new KnowledgeContext(
            "qry_001",
            Map.of("principal_id", "usr_001"),
            List.of("idxv_col_policy_active"),
            List.of(),
            List.of(new KnowledgeContext.ResultChunk(
                "col_policy",
                "doc_expense_policy",
                "chk_001",
                "dir_001",
                "Approved expenses are reimbursable.",
                List.of("Expense Policy"),
                List.of(new KnowledgeContext.PageSpan(1, 1)),
                0.91,
                "rerank_heuristic",
                "Matched."
            )),
            List.of(),
            List.of(),
            128,
            Map.of("debug_level", "basic")
        );

        String json = objectMapper.writeValueAsString(context);
        JsonNode tree = objectMapper.readTree(json);

        // Verify canonical names
        assertTrue(tree.has("evidence_items"),
            "Wire must use 'evidence_items'");
        assertTrue(tree.get("evidence_items").isArray(),
            "evidence_items must be an array");
        assertEquals(1, tree.get("evidence_items").size());

        JsonNode firstItem = tree.get("evidence_items").get(0);
        assertEquals("doc_expense_policy", firstItem.get("doc_id").asText(),
            "Evidence item must use 'doc_id'");
        assertEquals("chk_001", firstItem.get("evidence_id").asText(),
            "Evidence item must use 'evidence_id'");
        assertEquals("Approved expenses are reimbursable.", firstItem.get("content").asText(),
            "Evidence item must use 'content'");

        // Verify old names are absent
        assertFalse(tree.has("result_chunks"),
            "Wire must NOT contain 'result_chunks'");
        assertFalse(firstItem.has("final_doc_id"),
            "Evidence item must NOT contain 'final_doc_id'");
        assertFalse(firstItem.has("chunk_id"),
            "Evidence item must NOT contain 'chunk_id'");
        assertFalse(firstItem.has("display_text"),
            "Evidence item must NOT contain 'display_text'");

        assertFalse(json.contains("\"result_chunks\""),
            "Raw JSON must not contain 'result_chunks'");
        assertFalse(json.contains("\"final_doc_id\""),
            "Raw JSON must not contain 'final_doc_id'");
        assertFalse(json.contains("\"chunk_id\""),
            "Raw JSON must not contain 'chunk_id'");
        assertFalse(json.contains("\"display_text\""),
            "Raw JSON must not contain 'display_text'");
    }

    @Test
    void collectionRetrievalPlanIncludesTenantId() throws Exception {
        CollectionRetrievalPlan plan = new CollectionRetrievalPlan(
            "tnt_default",
            "col_policy",
            "idxv_col_policy_active",
            "os_col_policy",
            "qd_col_policy",
            "model-a",
            "chunk_default",
            Map.of("candidate_top_k", 20),
            "ret_default",
            1,
            "hash_001",
            Map.of(),
            Map.of(),
            false,
            List.of("doc_1"),
            Map.of()
        );

        String json = objectMapper.writeValueAsString(plan);
        JsonNode tree = objectMapper.readTree(json);

        assertEquals("tnt_default", tree.get("tenant_id").asText(),
            "Plan must include tenant_id");
        assertEquals("col_policy", tree.get("collection_id").asText());
    }
}

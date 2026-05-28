package com.realityrag.access.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * Real wire-format tests that verify cross-service serialization/deserialization
 * between access-service and retrieval-service contracts.
 *
 * These tests ensure the canonical wire names are consistent:
 * - query (not query_text)
 * - token_budget (not max_context_tokens)
 * - evidence_items (not result_chunks)
 * - doc_id (not final_doc_id)
 * - evidence_id (not chunk_id)
 * - content (not display_text)
 */
class AccessRetrievalWireTest {

    private final ObjectMapper objectMapper = new ObjectMapper()
        .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);

    @Test
    void accessInternalRequestUsesCanonicalWireNames() throws Exception {
        // Build the access-side internal request
        InternalRetrieveRequest accessRequest = new InternalRetrieveRequest(
            "qry_001",
            "trc_001",
            new InternalPrincipal(
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

        // Serialize access request to JSON wire format
        String json = objectMapper.writeValueAsString(accessRequest);
        JsonNode tree = objectMapper.readTree(json);

        // Verify canonical field names appear on the wire
        assertEquals("What expenses are reimbursable?", tree.get("query").asText(),
            "Wire format must use 'query'");
        assertEquals(1200, tree.get("token_budget").asInt(),
            "Wire format must use 'token_budget'");
        assertEquals("qry_001", tree.get("query_id").asText());
        assertEquals("trc_001", tree.get("trace_id").asText());
        assertEquals("ret_default", tree.get("retrieval_profile_id").asText());
        assertEquals("basic", tree.get("debug_level").asText());

        // Verify old field names do NOT appear
        assertTrue(tree.get("query_text") == null,
            "Wire format must NOT contain 'query_text'");
        assertTrue(tree.get("max_context_tokens") == null,
            "Wire format must NOT contain 'max_context_tokens'");

        // Verify the raw JSON string does not contain old names
        assertFalse(json.contains("\"query_text\""),
            "Raw JSON must not contain 'query_text'");
        assertFalse(json.contains("\"max_context_tokens\""),
            "Raw JSON must not contain 'max_context_tokens'");
    }

    @Test
    void accessKnowledgeContextAcceptsCanonicalWireNames() throws Exception {
        // Build JSON using canonical wire names (as retrieval service would send it)
        String retrievalJson = """
            {
              "query_id": "qry_001",
              "principal_context": {
                "principal_id": "usr_001",
                "permission_fingerprint": "perm:usr_001:col_policy"
              },
              "index_version_used": ["idxv_col_policy_active"],
              "collection_plans_used": [],
              "evidence_items": [
                {
                  "collection_id": "col_policy",
                  "doc_id": "doc_expense_policy",
                  "evidence_id": "chk_001",
                  "document_index_revision_id": "dir_001",
                  "content": "Approved expenses are reimbursable.",
                  "section_path": ["Expense Policy"],
                  "page_spans": [{"page_from": 1, "page_to": 1}],
                  "score": 0.91,
                  "source_stage": "rerank_heuristic",
                  "why_selected": "Matched reimbursable expenses policy."
                }
              ],
              "grouped_sources": [],
              "citations": [],
              "token_budget_used": 128,
              "retrieval_debug": {"debug_level": "basic"}
            }
            """;

        // Verify the JSON uses canonical names, not old names
        assertTrue(retrievalJson.contains("\"evidence_items\""),
            "Wire format must use 'evidence_items'");
        assertTrue(retrievalJson.contains("\"doc_id\""),
            "Wire format must use 'doc_id'");
        assertTrue(retrievalJson.contains("\"evidence_id\""),
            "Wire format must use 'evidence_id'");
        assertTrue(retrievalJson.contains("\"content\""),
            "Wire format must use 'content'");
        assertFalse(retrievalJson.contains("\"result_chunks\""),
            "Wire format must NOT contain 'result_chunks'");
        assertFalse(retrievalJson.contains("\"final_doc_id\""),
            "Wire format must NOT contain 'final_doc_id'");
        assertFalse(retrievalJson.contains("\"chunk_id\""),
            "Wire format must NOT contain 'chunk_id'");
        assertFalse(retrievalJson.contains("\"display_text\""),
            "Wire format must NOT contain 'display_text'");

        // Deserialize into access-side KnowledgeContext
        KnowledgeContext accessContext = objectMapper.readValue(retrievalJson, KnowledgeContext.class);

        // Assert all fields roundtrip correctly
        assertEquals("qry_001", accessContext.queryId());
        assertEquals(1, accessContext.resultChunks().size());

        KnowledgeContext.ResultChunk chunk = accessContext.resultChunks().get(0);
        assertEquals("doc_expense_policy", chunk.finalDocId());
        assertEquals("chk_001", chunk.chunkId());
        assertEquals("Approved expenses are reimbursable.", chunk.displayText());
        assertEquals(128, accessContext.tokenBudgetUsed());
    }
}

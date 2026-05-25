package com.realityrag.retrieval.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class InternalRetrieveControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void healthEndpointReturnsOk() throws Exception {
        mockMvc.perform(get("/health"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.service").value("retrieval"))
            .andExpect(jsonPath("$.status").value("ok"));
    }

    @Test
    void internalRetrieveReturnsKnowledgeContext() throws Exception {
        String body = """
            {
              "query_id": "qry_20260523_01",
              "trace_id": "trc_20260523_query_01",
              "principal": {
                "principal_id": "usr_finance_01",
                  "roles": ["employee"],
                "groups": ["finance"],
                "attributes": {
                  "region": "apac"
                }
              },
              "collection_scope": ["col_policy", "col_handbook"],
              "query_text": "What expenses are reimbursable?",
              "language": "en",
              "retrieval_profile_id": "ret_default",
              "filters": {
                "visibility": "internal"
              },
              "include_deprecated": false,
              "max_context_tokens": 1200,
              "debug_level": "basic"
            }
            """;

        mockMvc.perform(post("/internal/retrieve")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.query_id").value("qry_20260523_01"))
            .andExpect(jsonPath("$.collection_plans_used.length()").value(2))
            .andExpect(jsonPath("$.result_chunks.length()").value(2))
            .andExpect(jsonPath("$.result_chunks[0].source_stage").value("rerank_heuristic"))
            .andExpect(jsonPath("$.retrieval_debug.debug_level").value("basic"));
    }

    @Test
    void retrievalProfileEndpointReturnsDefaultProfile() throws Exception {
        mockMvc.perform(get("/internal/retrieval-profiles/ret_default"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.profile_id").value("ret_default"))
            .andExpect(jsonPath("$.candidate_top_k").value(20));
    }
}


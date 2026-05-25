package com.realityrag.retrieval.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
    "retrieval.search.enable-rerank=false"
})
class RerankDisabledRetrieveControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void retrieveSkipsRerankWhenSwitchDisabled() throws Exception {
        String body = """
            {
              "query_id": "qry_rerank_disabled_01",
              "trace_id": "trc_rerank_disabled_01",
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
            .andExpect(jsonPath("$.result_chunks[0].source_stage").value("hybrid_fusion"));
    }
}


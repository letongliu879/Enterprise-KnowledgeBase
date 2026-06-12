package com.realityrag.retrieval.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.realityrag.retrieval.AbstractPostgresTestBase;
import com.realityrag.retrieval.support.DbBackedRetrievalTestConfig;
import com.realityrag.retrieval.support.ProfileAndTocFixtureTestConfig;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@Import(ProfileAndTocFixtureTestConfig.class)
@TestPropertySource(properties = {
    "retrieval.data.retrieval-profiles-file=src/test/resources/projections/retrieval_profiles.jsonl",
    "retrieval.data.document-toc-file=src/test/resources/projections-ragflow/document_toc.jsonl"
})
class InternalRetrieveControllerTest extends AbstractPostgresTestBase {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DataSource dataSource;

    @BeforeEach
    void seedDb() {
        DbBackedRetrievalTestConfig.seed(DbBackedRetrievalTestConfig.jdbc(dataSource));
    }

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
                "user_id": "usr_finance_01",
                  "role_ids": ["employee"],
                "group_ids": ["finance"],
                "attributes": {
                  "region": "apac"
                }
              },
              "collection_scope": ["col_policy", "col_handbook"],
              "query": "What expenses are reimbursable?",
              "language": "en",
              "retrieval_profile_id": "ret_file",
              "filters": {
                "visibility": "internal"
              },
              "include_deprecated": false,
              "token_budget": 1200,
              "debug_level": "basic"
            }
            """;

        mockMvc.perform(post("/internal/retrieve")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.query_id").value("qry_20260523_01"))
            .andExpect(jsonPath("$.collection_plans_used.length()").value(2))
            .andExpect(jsonPath("$.evidence_items.length()").value(2))
            .andExpect(jsonPath("$.evidence_items[0].source_stage").value("rerank_heuristic"))
            .andExpect(jsonPath("$.retrieval_debug.debug_level").value("basic"));
    }

    @Test
    void retrievalProfileEndpointReturnsDefaultProfile() throws Exception {
        mockMvc.perform(get("/internal/retrieval-profiles/ret_file"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.profile_id").value("ret_file"))
            .andExpect(jsonPath("$.candidate_top_k").value(15));
    }
}


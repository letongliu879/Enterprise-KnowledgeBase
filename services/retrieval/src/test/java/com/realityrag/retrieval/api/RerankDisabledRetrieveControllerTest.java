package com.realityrag.retrieval.api;

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
    "retrieval.data.document-toc-file=src/test/resources/projections-ragflow/document_toc.jsonl",
    "retrieval.search.enable-rerank=false"
})
class RerankDisabledRetrieveControllerTest extends AbstractPostgresTestBase {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DataSource dataSource;

    @BeforeEach
    void seedDb() {
        DbBackedRetrievalTestConfig.seed(DbBackedRetrievalTestConfig.jdbc(dataSource));
    }

    @Test
    void retrieveSkipsRerankWhenSwitchDisabled() throws Exception {
        String body = """
            {
              "query_id": "qry_rerank_disabled_01",
              "trace_id": "trc_rerank_disabled_01",
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
            .andExpect(jsonPath("$.evidence_items[0].source_stage").value(org.hamcrest.Matchers.startsWith("hybrid_fusion")));
    }
}


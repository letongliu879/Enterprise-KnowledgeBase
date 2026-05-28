package com.realityrag.retrieval.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.realityrag.retrieval.support.FileFixtureRetrievalTestConfig;
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
@Import(FileFixtureRetrievalTestConfig.class)
@TestPropertySource(properties = {
    "retrieval.data.published-documents-file=src/test/resources/projections-ragflow/published_documents.jsonl",
    "retrieval.data.index-registry-file=src/test/resources/projections-ragflow/index_registry.jsonl",
    "retrieval.data.retrieval-profiles-file=src/test/resources/projections-ragflow/retrieval_profiles.jsonl",
    "retrieval.data.indexed-chunks-file=src/test/resources/projections-ragflow/indexed_chunks.jsonl",
    "retrieval.data.document-toc-file=src/test/resources/projections-ragflow/document_toc.jsonl",
    "retrieval.search.enable-neighbor-expansion=false",
    "retrieval.search.enable-breadcrumb-expansion=false",
    "retrieval.search.enable-ragflow-rank-features=false",
    "retrieval.search.enable-ragflow-children-aggregation=false",
    "retrieval.search.enable-ragflow-toc-aggregation=false"
})
class RagflowTocDisabledRetrieveControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void retrieveSkipsTocAggregationWhenSwitchDisabled() throws Exception {
        String body = """
            {
              "query_id": "qry_ragflow_toc_disabled_01",
              "trace_id": "trc_ragflow_toc_disabled_01",
              "principal": {
                "user_id": "usr_finance_01",
                  "role_ids": ["employee"],
                "group_ids": ["finance"],
                "attributes": {
                  "region": "apac"
                }
              },
              "collection_scope": ["col_policy"],
              "query": "receipt requirements",
              "language": "en",
              "retrieval_profile_id": "ret_ragflow",
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
            .andExpect(jsonPath("$.evidence_items[0].evidence_id").value("chk_policy_child_0002"))
            .andExpect(jsonPath("$.evidence_items[0].source_stage").value("rerank_heuristic"));
    }
}


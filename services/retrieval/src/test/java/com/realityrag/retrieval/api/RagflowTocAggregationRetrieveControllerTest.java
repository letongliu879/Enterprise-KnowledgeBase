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
    "retrieval.data.published-documents-file=src/test/resources/projections-ragflow/published_documents.jsonl",
    "retrieval.data.index-registry-file=src/test/resources/projections-ragflow/index_registry.jsonl",
    "retrieval.data.retrieval-profiles-file=src/test/resources/projections-ragflow/retrieval_profiles.jsonl",
    "retrieval.data.indexed-chunks-file=src/test/resources/projections-ragflow/indexed_chunks.jsonl",
    "retrieval.data.document-toc-file=src/test/resources/projections-ragflow/document_toc.jsonl",
    "retrieval.search.enable-neighbor-expansion=false",
    "retrieval.search.enable-breadcrumb-expansion=false",
    "retrieval.search.enable-ragflow-rank-features=false",
    "retrieval.search.enable-ragflow-children-aggregation=false",
    "retrieval.search.enable-ragflow-toc-aggregation=true"
})
class RagflowTocAggregationRetrieveControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void retrieveAddsChunksFromTocSelection() throws Exception {
        String body = """
            {
              "query_id": "qry_ragflow_toc_01",
              "trace_id": "trc_ragflow_toc_01",
              "principal": {
                "principal_id": "usr_finance_01",
                  "roles": ["employee"],
                "groups": ["finance"],
                "attributes": {
                  "region": "apac"
                }
              },
              "collection_scope": ["col_policy"],
              "query_text": "receipt requirements",
              "language": "en",
              "retrieval_profile_id": "ret_ragflow",
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
            .andExpect(jsonPath("$.result_chunks[0].chunk_id").value("chk_policy_other_0003"))
            .andExpect(jsonPath("$.result_chunks[0].source_stage").value("ragflow_toc_aggregate"));
    }
}


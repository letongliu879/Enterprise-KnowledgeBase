package com.realityrag.retrieval.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.realityrag.retrieval.support.FileFixtureRetrievalTestConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@Import(FileFixtureRetrievalTestConfig.class)
@TestPropertySource(properties = {
    "retrieval.data.published-documents-file=src/test/resources/projections-breadcrumb/published_documents.jsonl",
    "retrieval.data.index-registry-file=src/test/resources/projections-breadcrumb/index_registry.jsonl",
    "retrieval.data.retrieval-profiles-file=src/test/resources/projections-breadcrumb/retrieval_profiles.jsonl",
    "retrieval.data.indexed-chunks-file=src/test/resources/projections-breadcrumb/indexed_chunks.jsonl",
    "retrieval.data.document-toc-file=src/test/resources/projections-ragflow/document_toc.jsonl",
    "retrieval.search.enable-neighbor-expansion=false",
    "retrieval.search.enable-breadcrumb-expansion=true"
})
class BreadcrumbExpansionRetrieveControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void retrieveIncludesBreadcrumbSiblingChunks() throws Exception {
        String body = """
            {
              "query_id": "qry_breadcrumb_01",
              "trace_id": "trc_breadcrumb_01",
              "principal": {
                "user_id": "usr_finance_01",
                  "role_ids": ["employee"],
                "group_ids": ["finance"],
                "attributes": {
                  "region": "apac"
                }
              },
              "collection_scope": ["col_policy"],
              "query": "claims receipts",
              "language": "en",
              "retrieval_profile_id": "ret_breadcrumb",
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
            .andExpect(jsonPath("$.evidence_items.length()").value(3))
            .andExpect(jsonPath("$.evidence_items[0].evidence_id").value("chk_doc_expense_policy_idxv_col_policy_breadcrumb_0003"))
            .andExpect(jsonPath("$.evidence_items[1].source_stage").value("breadcrumb_expand"));
    }
}


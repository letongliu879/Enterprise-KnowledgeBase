package com.realityrag.retrieval.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
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
    "retrieval.data.published-documents-file=src/test/resources/projections/published_documents.jsonl",
    "retrieval.data.index-registry-file=src/test/resources/projections/index_registry.jsonl",
    "retrieval.data.retrieval-profiles-file=src/test/resources/projections/retrieval_profiles.jsonl",
    "retrieval.data.indexed-chunks-file=src/test/resources/projections/indexed_chunks.jsonl",
    "retrieval.data.document-toc-file=src/test/resources/projections-ragflow/document_toc.jsonl"
})
class FileProjectionRetrieveControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void fileBackedRetrieveUsesProjectionFiles() throws Exception {
        String body = """
            {
              "query_id": "qry_file_01",
              "trace_id": "trc_file_01",
              "principal": {
                "user_id": "usr_finance_01",
                  "role_ids": ["employee"],
                "group_ids": ["finance"],
                "attributes": {
                  "region": "apac"
                }
              },
              "collection_scope": ["col_policy", "col_handbook"],
              "query": "Which expenses are reimbursable?",
              "language": "en",
              "retrieval_profile_id": "ret_file",
              "filters": {
                "visibility": "internal"
              },
              "include_deprecated": false,
              "token_budget": 900,
              "debug_level": "basic"
            }
            """;

        mockMvc.perform(post("/internal/retrieve")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.collection_plans_used[0].active_index_version_id").value("idxv_col_policy_file"))
            .andExpect(jsonPath("$.collection_plans_used[0].profile_id").value("ret_file"))
            .andExpect(jsonPath("$.collection_plans_used[0].chunk_profile_id").value("chunk_file"))
            .andExpect(jsonPath("$.evidence_items.length()").value(2))
            .andExpect(jsonPath("$.evidence_items[0].evidence_id").exists())
            .andExpect(jsonPath("$.retrieval_debug.debug_ref").value("dbg://retrieval/qry_file_01"));
    }

    @Test
    void fileBackedProfileEndpointUsesProjectionFile() throws Exception {
        mockMvc.perform(get("/internal/retrieval-profiles/ret_file"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.profile_id").value("ret_file"))
            .andExpect(jsonPath("$.profile_version").value(7))
            .andExpect(jsonPath("$.chunk_profile_id").doesNotExist())
            .andExpect(jsonPath("$.candidate_top_k").value(15));
    }
}


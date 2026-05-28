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
    "retrieval.data.published-documents-file=src/test/resources/projections-metadata/published_documents.jsonl",
    "retrieval.data.index-registry-file=src/test/resources/projections-metadata/index_registry.jsonl",
    "retrieval.data.retrieval-profiles-file=src/test/resources/projections-metadata/retrieval_profiles.jsonl",
    "retrieval.data.indexed-chunks-file=src/test/resources/projections-metadata/indexed_chunks.jsonl",
    "retrieval.search.enable-neighbor-expansion=false",
    "retrieval.search.enable-breadcrumb-expansion=false"
})
class MetadataFilterRetrieveControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void retrieveAppliesManualMetaDataFilter() throws Exception {
        String body = """
            {
              "query_id": "qry_metadata_01",
              "trace_id": "trc_metadata_01",
              "principal": {
                "user_id": "usr_finance_01",
                  "role_ids": ["employee"],
                "group_ids": ["finance"],
                "attributes": {
                  "region": "apac"
                }
              },
              "collection_scope": ["col_policy"],
              "query": "approved expenses",
              "language": "en",
              "retrieval_profile_id": "ret_metadata",
              "meta_data_filter": {
                "method": "manual",
                "logic": "and",
                "manual": [
                  {"key": "region", "value": "apac", "op": "="}
                ]
              },
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
            .andExpect(jsonPath("$.evidence_items.length()").value(1))
            .andExpect(jsonPath("$.evidence_items[0].doc_id").value("doc_apac_policy"));
    }
}


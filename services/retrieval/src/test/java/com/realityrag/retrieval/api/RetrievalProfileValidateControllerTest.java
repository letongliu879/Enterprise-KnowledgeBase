package com.realityrag.retrieval.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.realityrag.retrieval.support.DbBackedRetrievalTestConfig;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = {
    "spring.datasource.url=jdbc:h2:mem:retrieval-validate;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.username=sa",
    "spring.datasource.password="
})
@AutoConfigureMockMvc
class RetrievalProfileValidateControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DataSource dataSource;

    @BeforeEach
    void seedDb() {
        DbBackedRetrievalTestConfig.seed(DbBackedRetrievalTestConfig.jdbc(dataSource));
    }

    @Test
    void validRetrievalProfileReturnsCanonicalConfigAndProfileHash() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-hybrid-v1",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "expansion_policy": {},
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default",
              "collection_id": "col-finance-policy",
              "version": "2"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(true))
            .andExpect(jsonPath("$.canonical_config.bm25_weight").value(0.3))
            .andExpect(jsonPath("$.canonical_config.vector_weight").value(0.7))
            .andExpect(jsonPath("$.canonical_config.candidate_top_k").value(20))
            .andExpect(jsonPath("$.canonical_config.similarity_threshold").value(0.75))
            .andExpect(jsonPath("$.canonical_config.rerank_enabled").value(true))
            .andExpect(jsonPath("$.canonical_config.rerank_model").value("bge-reranker-v2-m3"))
            .andExpect(jsonPath("$.canonical_config.fail_policy").value("fail_closed"))
            .andExpect(jsonPath("$.canonical_config.pack_budget").value(1200))
            .andExpect(jsonPath("$.profile_hash").value(org.hamcrest.Matchers.startsWith("sha256:")))
            .andExpect(jsonPath("$.runtime_owner").value("retrieval"))
            .andExpect(jsonPath("$.validator_version").value("1.0.0"))
            .andExpect(jsonPath("$.warnings").isArray())
            .andExpect(jsonPath("$.errors").isArray());
    }

    @Test
    void invalidWeightReturnsValidFalseWithErrors() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-invalid-weight",
              "profile_config": {
                "bm25_weight": 0.8,
                "vector_weight": 0.5,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "expansion_policy": {},
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(false))
            .andExpect(jsonPath("$.errors[?(@.code == 'BM25_VECTOR_WEIGHT_SUM')]").exists())
            .andExpect(jsonPath("$.canonical_config").doesNotExist());
    }

    @Test
    void invalidTopKReturnsValidFalseWithErrors() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-invalid-topk",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": -5,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "expansion_policy": {},
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(false))
            .andExpect(jsonPath("$.errors[?(@.code == 'INVALID_CANDIDATE_TOP_K')]").exists());
    }

    @Test
    void invalidTokenBudgetReturnsValidFalseWithErrors() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-invalid-budget",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "expansion_policy": {},
                "pack_budget": 0
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(false))
            .andExpect(jsonPath("$.errors[?(@.code == 'INVALID_PACK_BUDGET')]").exists());
    }

    @Test
    void invalidRerankModelReturnsValidFalseWithErrors() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-invalid-model",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "unknown-model",
                "fail_policy": "fail_closed",
                "expansion_policy": {},
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(false))
            .andExpect(jsonPath("$.errors[?(@.code == 'INVALID_RERANK_MODEL')]").exists());
    }

    @Test
    void invalidExpansionPolicyReturnsValidFalseWithErrors() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-invalid-expansion",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "expansion_policy": {
                  "type": "invalid_type"
                },
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(false))
            .andExpect(jsonPath("$.errors[?(@.code == 'INVALID_EXPANSION_TYPE')]").exists());
    }

    @Test
    void invalidFailPolicyReturnsValidFalseWithErrors() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-invalid-fail",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_sometimes",
                "expansion_policy": {},
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(false))
            .andExpect(jsonPath("$.errors[?(@.code == 'INVALID_FAIL_POLICY')]").exists());
    }

    @Test
    void canonicalHashIsStable() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-stable-hash",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "expansion_policy": {},
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        String hash1 = mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(true))
            .andReturn()
            .getResponse()
            .getContentAsString();

        String hash2 = mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(true))
            .andReturn()
            .getResponse()
            .getContentAsString();

        // Extract profile_hash from both responses and assert they are equal
        org.springframework.test.web.servlet.MvcResult result1 = mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(true))
            .andReturn();

        String response1 = result1.getResponse().getContentAsString();
        com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
        com.fasterxml.jackson.databind.JsonNode node1 = mapper.readTree(response1);
        String profileHash1 = node1.get("profile_hash").asText();

        org.springframework.test.web.servlet.MvcResult result2 = mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(true))
            .andReturn();

        String response2 = result2.getResponse().getContentAsString();
        com.fasterxml.jackson.databind.JsonNode node2 = mapper.readTree(response2);
        String profileHash2 = node2.get("profile_hash").asText();

        org.junit.jupiter.api.Assertions.assertEquals(profileHash1, profileHash2,
            "profile_hash must be stable across identical requests");
    }

    @Test
    void validateDoesNotModifyRetrievalProfilesTable() throws Exception {
        // First, count existing profiles
        var jdbc = DbBackedRetrievalTestConfig.jdbc(dataSource);
        int countBefore = jdbc.queryForObject("SELECT COUNT(*) FROM retrieval_profiles", Integer.class);

        String body = """
            {
              "retrieval_profile_id": "rp-no-side-effect",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "expansion_policy": {},
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(true));

        int countAfter = jdbc.queryForObject("SELECT COUNT(*) FROM retrieval_profiles", Integer.class);
        org.junit.jupiter.api.Assertions.assertEquals(countBefore, countAfter,
            "validate must not modify retrieval_profiles table");
    }

    @Test
    void validateDoesNotChangeActiveProfile() throws Exception {
        // Verify that the existing active profile remains unchanged after validation
        var jdbc = DbBackedRetrievalTestConfig.jdbc(dataSource);
        String hashBefore = jdbc.queryForObject(
            "SELECT profile_hash FROM retrieval_profiles WHERE profile_id = ? AND collection_id = ?",
            String.class, "ret_default", "col_policy");

        String body = """
            {
              "retrieval_profile_id": "rp-active-check",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "expansion_policy": {},
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(true));

        String hashAfter = jdbc.queryForObject(
            "SELECT profile_hash FROM retrieval_profiles WHERE profile_id = ? AND collection_id = ?",
            String.class, "ret_default", "col_policy");

        org.junit.jupiter.api.Assertions.assertEquals(hashBefore, hashAfter,
            "validate must not change active profile hash");
    }

    @Test
    void missingRequiredFieldsReturnsBadRequest() throws Exception {
        String body = """
            {
              "profile_config": {
                "bm25_weight": 0.3
              }
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isBadRequest());
    }

    @Test
    void highSimilarityThresholdReturnsWarning() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-high-threshold",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.95,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "expansion_policy": {},
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(true))
            .andExpect(jsonPath("$.warnings[?(@ =~ /.*above 0.9.*reduce recall.*/)]").exists());
    }

    @Test
    void canonicalConfigFillsDefaultsForMissingFields() throws Exception {
        String body = """
            {
              "retrieval_profile_id": "rp-defaults",
              "profile_config": {
                "bm25_weight": 0.3,
                "vector_weight": 0.7,
                "candidate_top_k": 20,
                "similarity_threshold": 0.75,
                "rerank_enabled": true,
                "rerank_model": "bge-reranker-v2-m3",
                "fail_policy": "fail_closed",
                "pack_budget": 1200
              },
              "tenant_id": "tnt_default"
            }
            """;

        mockMvc.perform(post("/internal/retrieval-profiles/validate")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.valid").value(true))
            .andExpect(jsonPath("$.canonical_config.expansion_policy").exists());
    }
}

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
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = {
    "spring.datasource.url=jdbc:h2:mem:retrieval-db-runtime;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.username=sa",
    "spring.datasource.password="
})
@AutoConfigureMockMvc
class DbBackedRuntimeRetrieveControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DataSource dataSource;

    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void seedDb() {
        jdbcTemplate = DbBackedRetrievalTestConfig.jdbc(dataSource);
        DbBackedRetrievalTestConfig.seed(jdbcTemplate);
    }

    @Test
    void runtimeUsesOnlyDbBackedProfilesIndexesChunksAndAudit() throws Exception {
        String body = """
            {
              "query_id": "qry_db_runtime_01",
              "trace_id": "trc_db_runtime_01",
              "principal": {
                "user_id": "usr_finance_01",
                "role_ids": ["employee"],
                "group_ids": ["finance"],
                "attributes": {}
              },
              "collection_scope": ["col_policy", "col_handbook"],
              "query": "What expenses are reimbursable?",
              "language": "en",
              "retrieval_profile_id": "ret_default",
              "filters": {
                "visibility": "internal",
                "principal_groups": ["finance"]
              },
              "include_deprecated": false,
              "token_budget": 1200,
              "debug_level": "basic"
            }
            """;

        String response = mockMvc.perform(post("/internal/retrieve")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.query_id").value("qry_db_runtime_01"))
            .andExpect(jsonPath("$.collection_plans_used.length()").value(2))
            .andDo(result -> System.out.println("RESPONSE: " + result.getResponse().getContentAsString()))
            .andExpect(jsonPath("$.evidence_items.length()").value(2))
            .andExpect(jsonPath("$.retrieval_debug.debug_ref").value("dbg://retrieval/qry_db_runtime_01"))
            .andReturn().getResponse().getContentAsString();

        Integer traceCount = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM run_traces WHERE run_trace_id = ? AND root_status = ? AND result_count = ?",
            Integer.class,
            "retrieval_qry_db_runtime_01",
            "SUCCEEDED",
            2
        );
        org.assertj.core.api.Assertions.assertThat(traceCount).isEqualTo(1);

        String details = jdbcTemplate.queryForObject(
            "SELECT details_json FROM run_steps WHERE trace_id = ? AND step_name = ?",
            String.class,
            "trc_db_runtime_01",
            "retrieval.response"
        );
        org.assertj.core.api.Assertions.assertThat(details)
            .contains("idxv_col_policy_active")
            .contains("chk_doc_expense_policy_idxv_col_policy_active_0001");
    }
}

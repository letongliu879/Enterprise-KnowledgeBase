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
    "spring.datasource.url=jdbc:h2:mem:retrieval-cache-purge;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.username=sa",
    "spring.datasource.password=",
    "retrieval.cache.provider=noop"
})
@AutoConfigureMockMvc
class CachePurgeControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DataSource dataSource;

    @BeforeEach
    void seedDb() {
        DbBackedRetrievalTestConfig.seed(DbBackedRetrievalTestConfig.jdbc(dataSource));
    }

    @Test
    void cachePurgeReturnsPurgedCount() throws Exception {
        String body = """
            {
              "tenant_id": "tenant_acme",
              "collection_id": "col_default",
              "doc_id": "doc_001",
              "evidence_id": "chunk_001"
            }
            """;

        mockMvc.perform(post("/internal/cache/purge")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.purged_count").value(0))
            .andExpect(jsonPath("$.scope.tenant_id").value("tenant_acme"))
            .andExpect(jsonPath("$.scope.collection_id").value("col_default"))
            .andExpect(jsonPath("$.scope.doc_id").value("doc_001"))
            .andExpect(jsonPath("$.scope.evidence_id").value("chunk_001"));
    }

    @Test
    void cachePurgeRequiresTenantId() throws Exception {
        String body = """
            {
              "collection_id": "col_default"
            }
            """;

        mockMvc.perform(post("/internal/cache/purge")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isBadRequest());
    }
}

package com.realityrag.access.api;

import static org.mockito.ArgumentMatchers.any;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.service.AccessGatewayService;
import com.realityrag.access.security.AccessRequestContextFilter;
import com.realityrag.access.support.AccessForbiddenException;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.BDDMockito.given;

@WebMvcTest(
    controllers = RetrieveController.class,
    excludeFilters = @ComponentScan.Filter(type = org.springframework.context.annotation.FilterType.ASSIGNABLE_TYPE, classes = AccessRequestContextFilter.class)
)
@Import(AccessExceptionHandler.class)
@AutoConfigureMockMvc(addFilters = false)
class RetrieveControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private AccessGatewayService accessGatewayService;

    @Test
    void retrieveReturnsKnowledgeContext() throws Exception {
        given(accessGatewayService.retrieve(any(), any())).willReturn(new KnowledgeContext(
            "qry_1",
            Map.of(),
            List.of("idx_v1"),
            List.of(),
            List.of(),
            List.of(),
            List.of(),
            256,
            Map.of()
        ));

        mockMvc.perform(post("/v1/retrieve")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {
                      "query": "what is ragflow",
                      "collection_scope": ["c1"]
                    }
                    """))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.query_id").value("qry_1"));
    }

    @Test
    void invalidDebugFailsValidation() throws Exception {
        mockMvc.perform(post("/v1/retrieve")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {
                      "query": "what is ragflow",
                      "collection_scope": ["c1"],
                      "debug": "verbose"
                    }
                    """))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error_code").value("ACC_INVALID_REQUEST"));
    }

    @Test
    void forbiddenMapsToExpectedError() throws Exception {
        given(accessGatewayService.retrieve(any(), any()))
            .willThrow(new AccessForbiddenException("Full debug is not allowed for this principal"));

        mockMvc.perform(post("/v1/retrieve")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {
                      "query": "what is ragflow",
                      "collection_scope": ["c1"],
                      "debug": "full"
                    }
                    """))
            .andExpect(status().isForbidden())
            .andExpect(jsonPath("$.error_code").value("ACC_FORBIDDEN"));
    }
}

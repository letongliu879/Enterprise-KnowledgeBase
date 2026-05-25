package com.realityrag.access.api;

import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.realityrag.access.health.RetrievalHealthProbe;
import com.realityrag.access.security.AccessRequestContextFilter;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(
    controllers = HealthController.class,
    excludeFilters = @ComponentScan.Filter(type = org.springframework.context.annotation.FilterType.ASSIGNABLE_TYPE, classes = AccessRequestContextFilter.class)
)
@AutoConfigureMockMvc(addFilters = false)
class HealthControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private RetrievalHealthProbe retrievalHealthProbe;

    @Test
    void healthReflectsRetrievalStatus() throws Exception {
        given(retrievalHealthProbe.probe()).willReturn("ok");

        mockMvc.perform(get("/health"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.service").value("access"))
            .andExpect(jsonPath("$.status").value("ok"))
            .andExpect(jsonPath("$.retrieval_status").value("ok"));
    }
}

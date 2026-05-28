package com.realityrag.retrieval.embedding;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.function.Executable;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

class OpenAiCompatibleQueryEmbeddingClientTest {

    private RetrievalBackendProperties properties;
    private ObjectMapper objectMapper;
    private OpenAiCompatibleQueryEmbeddingClient client;
    private RestTemplate restTemplate;

    @BeforeEach
    void setUp() throws Exception {
        properties = new RetrievalBackendProperties();
        objectMapper = new ObjectMapper();
        restTemplate = mock(RestTemplate.class);
        client = new OpenAiCompatibleQueryEmbeddingClient(properties, objectMapper);
        var field = OpenAiCompatibleQueryEmbeddingClient.class.getDeclaredField("restTemplate");
        field.setAccessible(true);
        field.set(client, restTemplate);
    }

    @Test
    void strictModeThrowsWhenApiKeyMissing() {
        properties.setLiveEmbeddingEnabled(true);
        properties.setEmbeddingBaseUrl("https://api.siliconflow.cn/v1");
        properties.setEmbeddingApiKey(""); // missing
        properties.setRequireLiveBackends(true);

        Executable action = () -> client.embed("test query", "BAAI/bge-m3");
        IllegalStateException ex = assertThrows(IllegalStateException.class, action);
        assertTrue(ex.getMessage().contains("not configured"));
    }

    @Test
    void strictModeThrowsWhenApiCallFails() {
        properties.setLiveEmbeddingEnabled(true);
        properties.setEmbeddingBaseUrl("https://api.siliconflow.cn/v1");
        properties.setEmbeddingApiKey("sk-test-key");
        properties.setRequireLiveBackends(true);
        when(restTemplate.exchange(anyString(), eq(HttpMethod.POST), any(), eq(String.class)))
            .thenThrow(new RestClientException("connection refused"));

        Executable action = () -> client.embed("test query", "BAAI/bge-m3");
        IllegalStateException ex = assertThrows(IllegalStateException.class, action);
        assertTrue(ex.getMessage().contains("API call failed"));
    }

    @Test
    void normalModeReturnsEmptyWhenApiKeyMissing() {
        properties.setLiveEmbeddingEnabled(true);
        properties.setEmbeddingBaseUrl("https://api.siliconflow.cn/v1");
        properties.setEmbeddingApiKey("");
        properties.setRequireLiveBackends(false);

        List<Double> result = client.embed("test query", "BAAI/bge-m3");
        assertTrue(result.isEmpty());
    }

    @Test
    void normalModeReturnsEmptyWhenLiveDisabled() {
        properties.setLiveEmbeddingEnabled(false);
        properties.setRequireLiveBackends(false);

        List<Double> result = client.embed("test query", "BAAI/bge-m3");
        assertTrue(result.isEmpty());
    }

    @Test
    void liveEmbeddingReturnsVector() {
        properties.setLiveEmbeddingEnabled(true);
        properties.setEmbeddingBaseUrl("https://api.siliconflow.cn/v1");
        properties.setEmbeddingApiKey("sk-test-key");
        properties.setEmbeddingModel("BAAI/bge-m3");

        String response = "{\"data\":[{\"embedding\":[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,"
            + "0.11,0.12,0.13,0.14,0.15,0.16]}]}";
        when(restTemplate.exchange(anyString(), eq(HttpMethod.POST), any(), eq(String.class)))
            .thenReturn(ResponseEntity.ok(response));

        List<Double> result = client.embed("test query", "BAAI/bge-m3");
        assertFalse(result.isEmpty());
        assertEquals(16, result.size());
        assertEquals(0.1, result.get(0), 0.001);
    }
}

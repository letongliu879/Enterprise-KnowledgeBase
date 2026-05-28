package com.realityrag.retrieval.embedding;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

public class OpenAiCompatibleQueryEmbeddingClient implements QueryEmbeddingClient {
    private static final Logger LOG = LoggerFactory.getLogger(OpenAiCompatibleQueryEmbeddingClient.class);

    private final RetrievalBackendProperties backendProperties;
    private final ObjectMapper objectMapper;
    private final RestTemplate restTemplate;

    public OpenAiCompatibleQueryEmbeddingClient(
        RetrievalBackendProperties backendProperties,
        ObjectMapper objectMapper
    ) {
        this.backendProperties = backendProperties;
        this.objectMapper = objectMapper;
        this.restTemplate = new RestTemplate();
    }

    @Override
    public List<Double> embed(String queryText, String embeddingModel) {
        if (!backendProperties.isLiveEmbeddingEnabled()
            || isBlank(backendProperties.getEmbeddingBaseUrl())
            || isBlank(backendProperties.getEmbeddingApiKey())) {
            if (backendProperties.isRequireLiveBackends()) {
                throw new IllegalStateException(
                    "Live embedding required but not configured (live-embedding-enabled="
                    + backendProperties.isLiveEmbeddingEnabled()
                    + ", embedding-base-url=" + backendProperties.getEmbeddingBaseUrl()
                    + ", embedding-api-key-present=" + !isBlank(backendProperties.getEmbeddingApiKey()) + ")");
            }
            return List.of();
        }

        String model = isBlank(embeddingModel) ? backendProperties.getEmbeddingModel() : embeddingModel;
        if (isBlank(model)) {
            if (backendProperties.isRequireLiveBackends()) {
                throw new IllegalStateException("Live embedding required but embedding model not configured");
            }
            return List.of();
        }

        String url = backendProperties.getEmbeddingBaseUrl().replaceAll("/+$", "") + "/embeddings";
        LinkedHashMap<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", model);
        payload.put("input", queryText == null ? "" : queryText);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(backendProperties.getEmbeddingApiKey());
        HttpEntity<java.util.Map<String, Object>> request = new HttpEntity<>(payload, headers);

        try {
            ResponseEntity<String> response = restTemplate.exchange(url, HttpMethod.POST, request, String.class);
            List<Double> vector = parseEmbedding(response.getBody() == null ? "" : response.getBody());
            LOG.info("SiliconFlow embedding succeeded, model={}, dimension={}", model, vector.size());
            return vector;
        } catch (RuntimeException error) {
            if (backendProperties.isRequireLiveBackends()) {
                throw new IllegalStateException(
                    "Live embedding required but API call failed: " + error.getMessage(), error);
            }
            LOG.warn("SiliconFlow embedding failed: {} — returning empty", error.getMessage());
            return List.of();
        }
    }

    private List<Double> parseEmbedding(String body) {
        try {
            JsonNode root = objectMapper.readTree(body);
            JsonNode data = root.path("data");
            if (!data.isArray() || data.isEmpty()) {
                return List.of();
            }
            JsonNode embedding = data.get(0).path("embedding");
            if (!embedding.isArray()) {
                return List.of();
            }
            List<Double> vector = new ArrayList<>();
            embedding.forEach(item -> vector.add(item.asDouble()));
            return vector;
        }
        catch (Exception error) {
            throw new IllegalStateException("Failed to parse embedding response", error);
        }
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}

package com.realityrag.retrieval.prompt;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

public class OpenAiCompatiblePromptModelClient implements PromptModelClient {
    private final RetrievalBackendProperties backendProperties;
    private final ObjectMapper objectMapper;
    private final RestTemplate restTemplate;

    public OpenAiCompatiblePromptModelClient(
        RetrievalBackendProperties backendProperties,
        ObjectMapper objectMapper
    ) {
        this.backendProperties = backendProperties;
        this.objectMapper = objectMapper;
        this.restTemplate = new RestTemplate();
    }

    @Override
    public Optional<String> complete(String systemPrompt, String userPrompt, double temperature) {
        if (!backendProperties.isLivePromptStrategiesEnabled()
            || isBlank(backendProperties.getPromptModelBaseUrl())
            || isBlank(backendProperties.getPromptModelApiKey())
            || isBlank(backendProperties.getPromptModelName())) {
            return Optional.empty();
        }

        String url = backendProperties.getPromptModelBaseUrl().replaceAll("/+$", "") + "/chat/completions";
        Map<String, Object> payload = Map.of(
            "model", backendProperties.getPromptModelName(),
            "temperature", temperature,
            "messages", List.of(
                Map.of("role", "system", "content", systemPrompt == null ? "" : systemPrompt),
                Map.of("role", "user", "content", userPrompt == null ? "" : userPrompt)
            )
        );

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(backendProperties.getPromptModelApiKey());
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);
        ResponseEntity<String> response = restTemplate.exchange(url, HttpMethod.POST, request, String.class);
        return parseContent(response.getBody() == null ? "" : response.getBody());
    }

    private Optional<String> parseContent(String body) {
        try {
            JsonNode root = objectMapper.readTree(body);
            JsonNode choices = root.path("choices");
            if (!choices.isArray() || choices.isEmpty()) {
                return Optional.empty();
            }
            String content = choices.get(0).path("message").path("content").asText("");
            return isBlank(content) ? Optional.empty() : Optional.of(content);
        } catch (Exception ignored) {
            return Optional.empty();
        }
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}

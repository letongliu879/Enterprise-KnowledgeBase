package com.realityrag.retrieval.config;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class RetrievalAgentAccessRegistry {
    private final Map<String, AgentAccessEntry> apiKeys;

    public RetrievalAgentAccessRegistry(RetrievalAgentAccessProperties properties) {
        LinkedHashMap<String, AgentAccessEntry> items = new LinkedHashMap<>();
        for (var entry : properties.getApiKeys().entrySet()) {
            var value = entry.getValue();
            items.put(entry.getKey(), new AgentAccessEntry(
                entry.getKey(),
                value.getAgentTypeId(),
                List.copyOf(value.getKnowledgeScopes()),
                List.copyOf(value.getRoles()),
                value.isDebugPermission(),
                value.getMaxContextTokens()
            ));
        }
        this.apiKeys = Map.copyOf(items);
    }

    public Map<String, AgentAccessEntry> entries() {
        return apiKeys;
    }

    public AgentAccessEntry get(String apiKeyId) {
        return apiKeys.get(apiKeyId);
    }

    public record AgentAccessEntry(
        String apiKeyId,
        String agentTypeId,
        List<String> knowledgeScopes,
        List<String> roles,
        boolean debugPermission,
        int maxContextTokens
    ) {}
}

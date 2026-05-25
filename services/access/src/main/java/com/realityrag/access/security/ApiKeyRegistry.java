package com.realityrag.access.security;

import com.realityrag.access.config.AccessSecurityProperties;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class ApiKeyRegistry {
    private final Map<String, AgentRegistration> registrations;

    public ApiKeyRegistry(AccessSecurityProperties properties) {
        LinkedHashMap<String, AgentRegistration> items = new LinkedHashMap<>();
        for (var entry : properties.getApiKeys().entrySet()) {
            var binding = entry.getValue();
            items.put(entry.getKey(), new AgentRegistration(
                entry.getKey(),
                binding.getAgentTypeId(),
                List.copyOf(binding.getKnowledgeScopes()),
                List.copyOf(binding.getRoles()),
                binding.isDebugPermission(),
                binding.getMaxContextTokens()
            ));
        }
        this.registrations = Map.copyOf(items);
    }

    public AgentRegistration resolve(String apiKey) {
        return registrations.get(apiKey);
    }

    public record AgentRegistration(
        String apiKeyId,
        String agentTypeId,
        List<String> knowledgeScopes,
        List<String> roles,
        boolean debugPermission,
        int maxContextTokens
    ) {}
}

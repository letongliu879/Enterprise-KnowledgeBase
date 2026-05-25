package com.realityrag.access.config;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "access.security")
public class AccessSecurityProperties {
    private Map<String, AgentBinding> apiKeys = new LinkedHashMap<>();

    public Map<String, AgentBinding> getApiKeys() {
        return apiKeys;
    }

    public void setApiKeys(Map<String, AgentBinding> apiKeys) {
        this.apiKeys = apiKeys == null ? new LinkedHashMap<>() : new LinkedHashMap<>(apiKeys);
    }

    public static class AgentBinding {
        private String agentTypeId;
        private List<String> knowledgeScopes = new ArrayList<>();
        private List<String> roles = new ArrayList<>();
        private boolean debugPermission;
        private int maxContextTokens = 4096;

        public String getAgentTypeId() {
            return agentTypeId;
        }

        public void setAgentTypeId(String agentTypeId) {
            this.agentTypeId = agentTypeId;
        }

        public List<String> getKnowledgeScopes() {
            return knowledgeScopes;
        }

        public void setKnowledgeScopes(List<String> knowledgeScopes) {
            this.knowledgeScopes = knowledgeScopes == null ? new ArrayList<>() : new ArrayList<>(knowledgeScopes);
        }

        public List<String> getRoles() {
            return roles;
        }

        public void setRoles(List<String> roles) {
            this.roles = roles == null ? new ArrayList<>() : new ArrayList<>(roles);
        }

        public boolean isDebugPermission() {
            return debugPermission;
        }

        public void setDebugPermission(boolean debugPermission) {
            this.debugPermission = debugPermission;
        }

        public int getMaxContextTokens() {
            return maxContextTokens;
        }

        public void setMaxContextTokens(int maxContextTokens) {
            this.maxContextTokens = maxContextTokens;
        }
    }
}

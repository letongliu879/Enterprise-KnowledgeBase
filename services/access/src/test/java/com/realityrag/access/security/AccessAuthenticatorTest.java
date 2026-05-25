package com.realityrag.access.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.realityrag.access.config.AccessSecurityProperties;
import com.realityrag.access.support.AccessUnauthenticatedException;
import com.realityrag.access.support.TestAgentAuthFactory;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class AccessAuthenticatorTest {
    private final AccessAuthenticator authenticator = new AccessAuthenticator(new ApiKeyRegistry(securityProperties()));

    @Test
    void apiKeyAuthenticatesAgentInstance() {
        var request = new MockHttpServletRequest("POST", "/mcp/messages");
        TestAgentAuthFactory.headers("POST", "/mcp/messages", "sessionId=s1")
            .forEach(request::addHeader);
        request.setQueryString("sessionId=s1");

        var context = authenticator.authenticate(request);
        assertEquals("rr-agent-platform-dev", context.apiKeyId());
        assertEquals("kb_assistant", context.agentTypeId());
        assertEquals("agent-instance-001", context.agentInstanceId());
        assertEquals("mcp_message", context.clientType());
    }

    @Test
    void unknownApiKeyFails() {
        var request = new MockHttpServletRequest("GET", "/sse");
        request.addHeader("X-API-Key", "unknown");
        request.addHeader("X-Agent-Instance-Id", "agent-x");

        assertThrows(AccessUnauthenticatedException.class, () -> authenticator.authenticate(request));
    }

    @Test
    void tenantAndPlatformHeadersAreIgnored() {
        var request = new MockHttpServletRequest("POST", "/v1/retrieve");
        request.addHeader("X-API-Key", TestAgentAuthFactory.API_KEY);
        request.addHeader("X-Agent-Instance-Id", "agent-instance-override");
        request.addHeader("X-Tenant-Id", "tenant-from-client");
        request.addHeader("X-Platform-Id", "platform-from-client");

        var context = authenticator.authenticate(request);
        assertEquals("agent-instance-override", context.agentInstanceId());
    }

    private AccessSecurityProperties securityProperties() {
        var value = new AccessSecurityProperties();
        var binding = new AccessSecurityProperties.AgentBinding();
        binding.setAgentTypeId("kb_assistant");
        binding.setKnowledgeScopes(java.util.List.of("col_policy", "col_finance"));
        binding.setRoles(java.util.List.of("agent"));
        binding.setDebugPermission(false);
        binding.setMaxContextTokens(4096);
        value.setApiKeys(Map.of(TestAgentAuthFactory.API_KEY, binding));
        return value;
    }
}

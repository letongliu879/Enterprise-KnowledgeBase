package com.realityrag.access.mcp;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.AccessApplication;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.service.AccessGatewayService;
import com.realityrag.access.support.TestAgentAuthFactory;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;
import java.util.Map;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;

@SpringBootTest(
    classes = AccessApplication.class,
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = {
        "spring.datasource.url=jdbc:h2:mem:access-mcp;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        "server.shutdown=immediate",
        "spring.lifecycle.timeout-per-shutdown-phase=1s"
    }
)
class SpringAiMcpServerTest {
    @LocalServerPort
    private int port;

    @MockBean
    private AccessGatewayService accessGatewayService;

    @Autowired
    private DataSource dataSource;

    @Autowired
    private ObjectMapper objectMapper;

    private HttpClient httpClient;
    private String mcpEndpoint;

    @BeforeAll
    static void beforeAll() {
        System.setProperty("file.encoding", "UTF-8");
    }

    @BeforeEach
    void setUp() {
        this.httpClient = HttpClient.newHttpClient();
        this.mcpEndpoint = "http://127.0.0.1:" + port + "/mcp";
        JdbcTemplate jdbcTemplate = new JdbcTemplate(dataSource);
        jdbcTemplate.execute("""
            CREATE TABLE IF NOT EXISTS api_key_projection (
                api_key_id VARCHAR(128) PRIMARY KEY,
                tenant_id VARCHAR(64) NOT NULL,
                agent_type_id VARCHAR(128) NOT NULL,
                knowledge_scopes VARCHAR(2048),
                roles VARCHAR(2048),
                debug_permission BOOLEAN NOT NULL DEFAULT FALSE,
                token_budget_limit INTEGER NOT NULL DEFAULT 4096,
                state VARCHAR(32) NOT NULL DEFAULT 'active',
                expires_at TIMESTAMP,
                projection_version INTEGER NOT NULL DEFAULT 1,
                last_updated_at TIMESTAMP NOT NULL,
                synced_at TIMESTAMP,
                runtime_synced BOOLEAN NOT NULL DEFAULT FALSE
            )
            """);
        jdbcTemplate.update("DELETE FROM api_key_projection");
        jdbcTemplate.update(
            """
                INSERT INTO api_key_projection (
                    api_key_id, tenant_id, agent_type_id, knowledge_scopes, roles,
                    debug_permission, token_budget_limit, state, expires_at,
                    projection_version, last_updated_at, runtime_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            TestAgentAuthFactory.API_KEY,
            "tnt_default",
            "kb_assistant",
            "[\"col_policy\",\"col_handbook\"]",
            "[\"agent\"]",
            false,
            4096,
            "active",
            null,
            1,
            java.time.Instant.now(),
            true
        );
    }

    @Test
    void mcpInitializeReturnsProtocolVersion() throws Exception {
        HttpResponse<String> response = postMcpMessage(
            TestAgentAuthFactory.API_KEY,
            TestAgentAuthFactory.AGENT_INSTANCE_ID,
            null,
            """
                {
                  "jsonrpc": "2.0",
                  "id": 1,
                  "method": "initialize","params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {
                      "name": "agent-platform-test",
                      "version": "1.0.0"
                    }
                  }
                }
                """
        );

        assertThat(response.statusCode()).isEqualTo(200);
        JsonNode body = objectMapper.readTree(extractMcpResponseBody(response.body()));
        System.out.println("=== INIT RESPONSE ===");
        System.out.println(objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(body));
        assertThat(body.get("jsonrpc").asText()).isEqualTo("2.0");
        assertThat(body.get("id").asInt()).isEqualTo(1);
        assertThat(body.get("result").get("protocolVersion").asText()).isEqualTo("2025-11-25");
    }

    @Test
    void mcpListsSearchEnterpriseKnowledgeTool() throws Exception {
        HttpResponse<String> initResponse = postMcpMessage(
            TestAgentAuthFactory.API_KEY,
            TestAgentAuthFactory.AGENT_INSTANCE_ID,
            null,
            """
                {
                  "jsonrpc": "2.0",
                  "id": 1,
                  "method": "initialize",
                  "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {
                      "name": "agent-platform-test",
                      "version": "1.0.0"
                    }
                  }
                }
                """
        );
        assertThat(initResponse.statusCode()).isEqualTo(200);
        String sessionId = initResponse.headers().firstValue("Mcp-Session-Id").orElse(null);

        HttpResponse<String> toolsResponse = postMcpMessage(
            TestAgentAuthFactory.API_KEY,
            TestAgentAuthFactory.AGENT_INSTANCE_ID,
            sessionId,
            """
                {
                  "jsonrpc": "2.0",
                  "id": 2,
                  "method": "tools/list"
                }
                """
        );

        assertThat(toolsResponse.statusCode()).isEqualTo(200);
        JsonNode body = objectMapper.readTree(extractMcpResponseBody(toolsResponse.body()));
        JsonNode tools = body.get("result").get("tools");
        assertThat(tools.isArray()).isTrue();
        List<String> toolNames = new java.util.ArrayList<>();
        tools.forEach(tool -> toolNames.add(tool.get("name").asText()));
        assertThat(toolNames).contains("search_enterprise_knowledge");
    }

    @Test
    void mcpCallsSearchEnterpriseKnowledgeTool() throws Exception {
        given(accessGatewayService.retrieveWithContext(any(), any())).willReturn(new KnowledgeContext(
            "qry_mcp_1",
            Map.of("agent_type_id", "kb_assistant"),
            List.of("idx_v1"),
            List.of(),
            List.of(),
            List.of(),
            List.of(),
            0,
            Map.of("debug_level", "none")
        ));

        HttpResponse<String> initResponse = postMcpMessage(
            TestAgentAuthFactory.API_KEY,
            TestAgentAuthFactory.AGENT_INSTANCE_ID,
            null,
            """
                {
                  "jsonrpc": "2.0",
                  "id": 1,
                  "method": "initialize",
                  "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {
                      "name": "agent-platform-test",
                      "version": "1.0.0"
                    }
                  }
                }
                """
        );
        assertThat(initResponse.statusCode()).isEqualTo(200);
        String sessionId = initResponse.headers().firstValue("Mcp-Session-Id").orElse(null);

        HttpResponse<String> toolResponse = postMcpMessage(
            TestAgentAuthFactory.API_KEY,
            TestAgentAuthFactory.AGENT_INSTANCE_ID,
            sessionId,
            """
                {
                  "jsonrpc": "2.0",
                  "id": 3,
                  "method": "tools/call",
                  "params": {
                    "name": "search_enterprise_knowledge",
                    "arguments": {
                      "query": "What expenses are reimbursable?",
                      "knowledge_scope": "col_policy",
                      "debug": "none"
                    }
                  }
                }
                """
        );

        assertThat(toolResponse.statusCode()).isEqualTo(200);
        JsonNode body = objectMapper.readTree(extractMcpResponseBody(toolResponse.body()));
        JsonNode content = body.get("result").get("content");
        assertThat(content.isArray()).isTrue();
        assertThat(content.size()).isGreaterThan(0);
        String text = content.get(0).get("text").asText();
        assertThat(text).contains("qry_mcp_1");
    }

    @Test
    void mcpRejectsUnauthenticatedRequest() throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(mcpEndpoint))
            .header("Content-Type", "application/json")
            .header("Accept", "text/event-stream")
            .header("Accept", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString("""
                {
                  "jsonrpc": "2.0",
                  "id": 1,
                  "method": "initialize",
                  "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                      "name": "test-client",
                      "version": "1.0.0"
                    }
                  }
                }
                """))
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isEqualTo(401);
        // Response may be SSE format or JSON depending on server behavior for auth failures
        String responseBody = response.body();
        assertThat(responseBody).contains("UNAUTHENTICATED");
    }

    @Test
    void mcpRejectsInvalidApiKey() throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(mcpEndpoint))
            .header("Content-Type", "application/json")
            .header("Accept", "text/event-stream")
            .header("Accept", "application/json")
            .header("X-API-Key", "invalid-key")
            .header("X-Agent-Instance-Id", "test-instance")
            .POST(HttpRequest.BodyPublishers.ofString("""
                {
                  "jsonrpc": "2.0",
                  "id": 1,
                  "method": "initialize",
                  "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                      "name": "test-client",
                      "version": "1.0.0"
                    }
                  }
                }
                """))
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isEqualTo(401);
        // Response may be SSE format or JSON depending on server behavior for auth failures
        String responseBody = response.body();
        assertThat(responseBody).contains("UNAUTHENTICATED");
    }

    @Test
    void mcpRejectsSessionPrincipalDrift() throws Exception {
        // Step 1: Initialize with agent-instance-A
        HttpResponse<String> initResponse = postMcpMessage(
            TestAgentAuthFactory.API_KEY,
            "agent-instance-A",
            null,
            """
                {
                  "jsonrpc": "2.0",
                  "id": 1,
                  "method": "initialize",
                  "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {
                      "name": "agent-platform-test",
                      "version": "1.0.0"
                    }
                  }
                }
                """
        );
        assertThat(initResponse.statusCode()).isEqualTo(200);
        String sessionId = initResponse.headers().firstValue("Mcp-Session-Id").orElse(null);
        assertThat(sessionId).isNotNull();

        // Step 2: Reuse sessionId but with agent-instance-B - should be rejected
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(mcpEndpoint))
            .header("Content-Type", "application/json")
            .header("Accept", "text/event-stream")
            .header("Accept", "application/json")
            .header("X-API-Key", TestAgentAuthFactory.API_KEY)
            .header("X-Agent-Instance-Id", "agent-instance-B")
            .header("Mcp-Session-Id", sessionId)
            .POST(HttpRequest.BodyPublishers.ofString("""
                {
                  "jsonrpc": "2.0",
                  "id": 2,
                  "method": "tools/list"
                }
                """))
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isEqualTo(403);
        String responseBody = response.body();
        assertThat(responseBody).containsIgnoringCase("principal");
    }

    private HttpResponse<String> postMcpMessage(String apiKey, String agentInstanceId, String sessionId, String body) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
            .uri(URI.create(mcpEndpoint))
            .header("Content-Type", "application/json")
            .header("Accept", "text/event-stream")
            .header("Accept", "application/json");

        if (sessionId != null && !sessionId.isBlank()) {
            builder.header("Mcp-Session-Id", sessionId);
        }

        if (apiKey != null) {
            builder.header("X-API-Key", apiKey);
        }
        if (agentInstanceId != null) {
            builder.header("X-Agent-Instance-Id", agentInstanceId);
        }

        return httpClient.send(
            builder.POST(HttpRequest.BodyPublishers.ofString(body)).build(),
            HttpResponse.BodyHandlers.ofString()
        );
    }

    /**
     * Parse MCP Streamable HTTP response body.
     * The server may return either:
     * - Plain JSON (when Accept includes application/json and no SSE streaming is needed)
     * - SSE format (when Accept includes text/event-stream)
     * This method handles both for test compatibility.
     */
    private String extractMcpResponseBody(String responseBody) {
        // Plain JSON response
        if (responseBody.trim().startsWith("{")) {
            return responseBody;
        }
        // SSE format: extract data line
        for (String line : responseBody.split("\n")) {
            if (line.startsWith("data:")) {
                return line.substring("data:".length()).trim();
            }
        }
        throw new IllegalStateException("Unable to parse MCP response: " + responseBody);
    }
}

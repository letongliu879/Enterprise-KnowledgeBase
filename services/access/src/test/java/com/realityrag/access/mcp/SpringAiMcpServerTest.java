package com.realityrag.access.mcp;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.AccessApplication;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.service.AccessGatewayService;
import com.realityrag.access.support.TestAgentAuthFactory;
import io.modelcontextprotocol.client.McpClient;
import io.modelcontextprotocol.client.McpSyncClient;
import io.modelcontextprotocol.client.transport.HttpClientSseClientTransport;
import io.modelcontextprotocol.spec.McpSchema;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.boot.test.web.server.LocalServerPort;

@SpringBootTest(
    classes = AccessApplication.class,
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = {
        "server.shutdown=immediate",
        "spring.lifecycle.timeout-per-shutdown-phase=1s"
    }
)
class SpringAiMcpServerTest {
    @LocalServerPort
    private int port;

    @MockBean
    private AccessGatewayService accessGatewayService;

    private HttpClient httpClient;

    @BeforeEach
    void setUp() {
        this.httpClient = HttpClient.newHttpClient();
    }

    @Test
    void agentStyleMcpFlowListsAndCallsGovernedTool() {
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

        try (McpSyncClient client = buildClient(TestAgentAuthFactory.AGENT_INSTANCE_ID)) {
            McpSchema.InitializeResult initializeResult = client.initialize();
            assertThat(initializeResult.protocolVersion()).isEqualTo("2024-11-05");

            McpSchema.ListToolsResult toolsResult = client.listTools();
            assertThat(toolsResult.tools())
                .extracting(McpSchema.Tool::name)
                .contains("search_enterprise_knowledge");

            McpSchema.CallToolResult toolResult = client.callTool(new McpSchema.CallToolRequest(
                "search_enterprise_knowledge",
                Map.of(
                    "query", "What expenses are reimbursable?",
                    "knowledge_scope", "col_policy",
                    "retrieval_profile_id", "ret_default",
                    "debug", "none"
                )
            ));

            List<String> texts = toolResult.content().stream()
                .filter(item -> item instanceof McpSchema.TextContent)
                .map(item -> ((McpSchema.TextContent) item).text())
                .toList();
            assertThat(texts).isNotEmpty();
            assertThat(toolResult.isError())
                .withFailMessage("Unexpected MCP tool error content: %s", texts)
                .isFalse();
            assertThat(texts).anyMatch(text -> text.contains("qry_mcp_1"));
        }
    }

    @Test
    void mcpSessionRejectsAgentInstanceDrift() {
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

        try {
            SseSession session = openSseSession("agent-instance-A");
            String endpoint = session.endpoint();
            String sessionId = endpoint.substring(endpoint.indexOf("sessionId=") + "sessionId=".length());

            HttpResponse<String> response = postMcpMessage(sessionId, "agent-instance-B", """
                {
                  "jsonrpc": "2.0",
                  "id": 1,
                  "method": "initialize",
                  "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                      "name": "agent-platform-test",
                      "version": "1.0.0"
                    }
                  }
                }
                """);

            assertThat(response.statusCode()).isEqualTo(403);
            assertThat(response.body()).contains("principal");
            session.close();
        }
        catch (Exception error) {
            throw new RuntimeException(error);
        }
    }

    private McpSyncClient buildClient(String agentInstanceId) {
        String baseUrl = "http://127.0.0.1:" + port;
        HttpClientSseClientTransport transport = new HttpClientSseClientTransport(
            HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)),
            HttpRequest.newBuilder()
                .header("X-API-Key", TestAgentAuthFactory.API_KEY)
                .header("X-Agent-Instance-Id", agentInstanceId),
            baseUrl,
            "/sse",
            new ObjectMapper()
        );

        return McpClient.sync(transport)
            .requestTimeout(Duration.ofSeconds(10))
            .initializationTimeout(Duration.ofSeconds(10))
            .clientInfo(new McpSchema.Implementation("agent-platform-test", "1.0.0"))
            .build();
    }

    private SseSession openSseSession(String agentInstanceId) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) URI.create("http://127.0.0.1:" + port + "/sse")
            .toURL()
            .openConnection();
        connection.setRequestMethod("GET");
        TestAgentAuthFactory.headers("GET", "/sse", null, agentInstanceId)
            .forEach(connection::setRequestProperty);
        connection.setRequestProperty("Accept", "text/event-stream");
        connection.connect();
        assertThat(connection.getResponseCode()).isEqualTo(200);
        BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8));
        String line;
        while ((line = reader.readLine()) != null) {
            if (line.startsWith("data:")) {
                return new SseSession(connection, reader, line.substring("data:".length()).trim());
            }
        }
        connection.disconnect();
        throw new IllegalStateException("No endpoint data found in SSE body");
    }

    private HttpResponse<String> postMcpMessage(String sessionId, String agentInstanceId, String body) throws Exception {
        String query = "sessionId=" + sessionId;
        HttpRequest.Builder builder = HttpRequest.newBuilder()
            .uri(URI.create("http://127.0.0.1:" + port + "/mcp/messages?" + query))
            .header("Content-Type", "application/json");
        TestAgentAuthFactory.headers("POST", "/mcp/messages", query, agentInstanceId)
            .forEach(builder::header);
        return httpClient.send(
            builder.POST(HttpRequest.BodyPublishers.ofString(body)).build(),
            HttpResponse.BodyHandlers.ofString()
        );
    }

    private record SseSession(HttpURLConnection connection, BufferedReader reader, String endpoint) {
        void close() throws Exception {
            reader.close();
            connection.disconnect();
        }
    }
}

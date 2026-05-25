package com.realityrag.access.mcp;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.security.McpSessionPrincipalBindingStore;
import io.modelcontextprotocol.server.transport.WebMvcSseServerTransportProvider;
import io.modelcontextprotocol.spec.McpServerTransportProvider;
import java.util.Arrays;
import java.util.List;
import org.springframework.ai.mcp.server.autoconfigure.McpServerProperties;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.function.RouterFunction;
import org.springframework.web.servlet.function.ServerResponse;

@Configuration
public class McpServerConfig {
    @Bean
    List<ToolCallback> accessMcpTools(McpAccessTools tools) {
        return Arrays.asList(MethodToolCallbackProvider.builder()
            .toolObjects(tools)
            .build()
            .getToolCallbacks());
    }

    @Bean
    McpServerTransportProvider mcpServerTransportProvider(
        ObjectMapper objectMapper,
        McpServerProperties serverProperties,
        McpSessionPrincipalBindingStore bindingStore
    ) {
        var delegate = new WebMvcSseServerTransportProvider(
            objectMapper,
            serverProperties.getBaseUrl(),
            serverProperties.getSseMessageEndpoint(),
            serverProperties.getSseEndpoint()
        );
        return new AccessMcpTransportProvider(delegate, bindingStore);
    }

    @Bean
    RouterFunction<ServerResponse> mvcMcpRouterFunction(McpServerTransportProvider transportProvider) {
        if (transportProvider instanceof AccessMcpTransportProvider wrapped) {
            return wrapped.routerFunction();
        }
        throw new IllegalStateException("Unexpected MCP transport provider type");
    }
}

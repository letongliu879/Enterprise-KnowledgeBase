package com.realityrag.access.mcp;

import java.util.List;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class McpServerConfig {
    @Bean
    List<ToolCallback> accessMcpTools(McpAccessTools tools) {
        return List.of(MethodToolCallbackProvider.builder()
            .toolObjects(tools)
            .build()
            .getToolCallbacks());
    }
}

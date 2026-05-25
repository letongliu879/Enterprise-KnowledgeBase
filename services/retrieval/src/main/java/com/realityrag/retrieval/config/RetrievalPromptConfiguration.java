package com.realityrag.retrieval.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.prompt.NoOpPromptModelClient;
import com.realityrag.retrieval.prompt.OpenAiCompatiblePromptModelClient;
import com.realityrag.retrieval.prompt.PromptModelClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RetrievalPromptConfiguration {
    @Bean
    public PromptModelClient promptModelClient(
        RetrievalBackendProperties backendProperties,
        ObjectMapper objectMapper
    ) {
        if (backendProperties.isLivePromptStrategiesEnabled()) {
            return new OpenAiCompatiblePromptModelClient(backendProperties, objectMapper);
        }
        return new NoOpPromptModelClient();
    }
}

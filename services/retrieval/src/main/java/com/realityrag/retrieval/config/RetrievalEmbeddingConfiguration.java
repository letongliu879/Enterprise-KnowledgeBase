package com.realityrag.retrieval.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.embedding.OpenAiCompatibleQueryEmbeddingClient;
import com.realityrag.retrieval.embedding.QueryEmbeddingClient;
import com.realityrag.retrieval.embedding.StubQueryEmbeddingClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RetrievalEmbeddingConfiguration {
    @Bean
    public QueryEmbeddingClient queryEmbeddingClient(
        RetrievalBackendProperties backendProperties,
        ObjectMapper objectMapper
    ) {
        if (backendProperties.isLiveEmbeddingEnabled()) {
            return new OpenAiCompatibleQueryEmbeddingClient(backendProperties, objectMapper);
        }
        return new StubQueryEmbeddingClient();
    }
}

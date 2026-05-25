package com.realityrag.retrieval.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.profiles.FileProjectionRetrievalProfileStore;
import com.realityrag.retrieval.profiles.InMemoryRetrievalProfileStore;
import com.realityrag.retrieval.profiles.RetrievalProfileStore;
import com.realityrag.retrieval.scope.sources.FileProjectionIndexRegistrySource;
import com.realityrag.retrieval.scope.sources.FileProjectionPublishedDocumentSource;
import com.realityrag.retrieval.scope.sources.InMemoryIndexRegistrySource;
import com.realityrag.retrieval.scope.sources.InMemoryPublishedDocumentSource;
import com.realityrag.retrieval.scope.sources.IndexRegistrySource;
import com.realityrag.retrieval.scope.sources.PublishedDocumentSource;
import com.realityrag.retrieval.store.FileProjectionKnowledgeStore;
import com.realityrag.retrieval.store.InMemoryKnowledgeStore;
import com.realityrag.retrieval.store.KnowledgeStore;
import com.realityrag.retrieval.toc.DocumentTocSource;
import com.realityrag.retrieval.toc.FileProjectionDocumentTocSource;
import com.realityrag.retrieval.toc.InMemoryDocumentTocSource;
import java.nio.file.Path;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties({
    RetrievalDataProperties.class,
    RetrievalBackendProperties.class,
    RetrievalSearchStrategyProperties.class
})
public class RetrievalDataConfiguration {
    @Bean
    public PublishedDocumentSource publishedDocumentSource(
        RetrievalDataProperties properties,
        ObjectMapper objectMapper
    ) {
        if (hasText(properties.getPublishedDocumentsFile())) {
            return new FileProjectionPublishedDocumentSource(
                Path.of(properties.getPublishedDocumentsFile()),
                objectMapper
            );
        }
        return new InMemoryPublishedDocumentSource();
    }

    @Bean
    public IndexRegistrySource indexRegistrySource(
        RetrievalDataProperties properties,
        ObjectMapper objectMapper
    ) {
        if (hasText(properties.getIndexRegistryFile())) {
            return new FileProjectionIndexRegistrySource(
                Path.of(properties.getIndexRegistryFile()),
                objectMapper
            );
        }
        return new InMemoryIndexRegistrySource();
    }

    @Bean
    public RetrievalProfileStore retrievalProfileStore(
        RetrievalDataProperties properties,
        ObjectMapper objectMapper
    ) {
        if (hasText(properties.getRetrievalProfilesFile())) {
            return new FileProjectionRetrievalProfileStore(
                Path.of(properties.getRetrievalProfilesFile()),
                objectMapper
            );
        }
        return new InMemoryRetrievalProfileStore();
    }

    @Bean
    public KnowledgeStore knowledgeStore(
        RetrievalDataProperties properties,
        ObjectMapper objectMapper
    ) {
        if (hasText(properties.getIndexedChunksFile())) {
            return new FileProjectionKnowledgeStore(
                Path.of(properties.getIndexedChunksFile()),
                objectMapper
            );
        }
        return new InMemoryKnowledgeStore();
    }

    @Bean
    public DocumentTocSource documentTocSource(
        RetrievalDataProperties properties,
        ObjectMapper objectMapper
    ) {
        if (hasText(properties.getDocumentTocFile())) {
            return new FileProjectionDocumentTocSource(
                Path.of(properties.getDocumentTocFile()),
                objectMapper
            );
        }
        return new InMemoryDocumentTocSource();
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}

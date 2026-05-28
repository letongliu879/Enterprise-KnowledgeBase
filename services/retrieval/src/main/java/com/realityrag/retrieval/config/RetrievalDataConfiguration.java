package com.realityrag.retrieval.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.profiles.JdbcRetrievalProfileStore;
import com.realityrag.retrieval.profiles.RetrievalProfileStore;
import com.realityrag.retrieval.scope.sources.IndexRegistrySource;
import com.realityrag.retrieval.scope.sources.JdbcIndexRegistrySource;
import com.realityrag.retrieval.scope.sources.JdbcPublishedDocumentSource;
import com.realityrag.retrieval.scope.sources.PublishedDocumentSource;
import com.realityrag.retrieval.store.JdbcChunkRegistryKnowledgeStore;
import com.realityrag.retrieval.cache.RetrievalCacheProperties;
import com.realityrag.retrieval.store.KnowledgeStore;
import com.realityrag.retrieval.toc.DocumentTocSource;
import com.realityrag.retrieval.toc.JdbcDocumentTocSource;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

@Configuration
@EnableConfigurationProperties({
    RetrievalBackendProperties.class,
    RetrievalSearchStrategyProperties.class,
    RetrievalCacheProperties.class
})
public class RetrievalDataConfiguration {
    @Bean
    @ConditionalOnMissingBean(PublishedDocumentSource.class)
    public PublishedDocumentSource publishedDocumentSource(
        JdbcTemplate jdbcTemplate
    ) {
        return new JdbcPublishedDocumentSource(jdbcTemplate);
    }

    @Bean
    @ConditionalOnMissingBean(IndexRegistrySource.class)
    public IndexRegistrySource indexRegistrySource(
        JdbcTemplate jdbcTemplate
    ) {
        return new JdbcIndexRegistrySource(jdbcTemplate);
    }

    @Bean
    @ConditionalOnMissingBean(RetrievalProfileStore.class)
    public RetrievalProfileStore retrievalProfileStore(
        JdbcTemplate jdbcTemplate,
        ObjectMapper objectMapper
    ) {
        return new JdbcRetrievalProfileStore(jdbcTemplate, objectMapper);
    }

    @Bean
    @ConditionalOnMissingBean(KnowledgeStore.class)
    public KnowledgeStore knowledgeStore(
        JdbcTemplate jdbcTemplate,
        ObjectMapper objectMapper
    ) {
        return new JdbcChunkRegistryKnowledgeStore(jdbcTemplate, objectMapper);
    }

    @Bean
    @ConditionalOnMissingBean(DocumentTocSource.class)
    public DocumentTocSource documentTocSource(
        JdbcTemplate jdbcTemplate,
        ObjectMapper objectMapper
    ) {
        return new JdbcDocumentTocSource(jdbcTemplate, objectMapper);
    }
}

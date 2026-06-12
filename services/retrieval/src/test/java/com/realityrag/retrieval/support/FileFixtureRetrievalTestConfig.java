package com.realityrag.retrieval.support;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.profiles.FileProjectionRetrievalProfileStore;
import com.realityrag.retrieval.profiles.RetrievalProfileStore;
import com.realityrag.retrieval.scope.sources.FileProjectionIndexRegistrySource;
import com.realityrag.retrieval.scope.sources.FileProjectionPublishedDocumentSource;
import com.realityrag.retrieval.scope.sources.IndexRegistrySource;
import com.realityrag.retrieval.scope.sources.PublishedDocumentSource;
import com.realityrag.retrieval.store.FileProjectionKnowledgeStore;
import com.realityrag.retrieval.store.KnowledgeStore;
import com.realityrag.retrieval.toc.DocumentTocSource;
import com.realityrag.retrieval.toc.FileProjectionDocumentTocSource;
import java.nio.file.Path;
import javax.sql.DataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.core.JdbcTemplate;

@TestConfiguration
public class FileFixtureRetrievalTestConfig {
    @Bean
    @Primary
    public JdbcTemplate fixtureJdbcTemplate(DataSource dataSource) {
        return new JdbcTemplate(dataSource);
    }

    @Bean
    @Primary
    public PublishedDocumentSource publishedDocumentSource(
        @Value("${retrieval.data.published-documents-file}") String publishedDocumentsFile,
        ObjectMapper objectMapper
    ) {
        return new FileProjectionPublishedDocumentSource(Path.of(publishedDocumentsFile), objectMapper);
    }

    @Bean
    @Primary
    public IndexRegistrySource indexRegistrySource(
        @Value("${retrieval.data.index-registry-file}") String indexRegistryFile,
        ObjectMapper objectMapper
    ) {
        return new FileProjectionIndexRegistrySource(Path.of(indexRegistryFile), objectMapper);
    }

    @Bean
    @Primary
    public RetrievalProfileStore retrievalProfileStore(
        @Value("${retrieval.data.retrieval-profiles-file}") String retrievalProfilesFile,
        ObjectMapper objectMapper
    ) {
        return new FileProjectionRetrievalProfileStore(Path.of(retrievalProfilesFile), objectMapper);
    }

    @Bean
    @Primary
    public KnowledgeStore knowledgeStore(
        @Value("${retrieval.data.indexed-chunks-file}") String indexedChunksFile,
        ObjectMapper objectMapper
    ) {
        return new FileProjectionKnowledgeStore(Path.of(indexedChunksFile), objectMapper);
    }

    @Bean
    @Primary
    public DocumentTocSource documentTocSource(
        @Value("${retrieval.data.document-toc-file:}") String documentTocFile,
        ObjectMapper objectMapper
    ) {
        if (documentTocFile == null || documentTocFile.isBlank()) {
            return (collectionId, finalDocId) -> java.util.List.of();
        }
        return new FileProjectionDocumentTocSource(Path.of(documentTocFile), objectMapper);
    }
}

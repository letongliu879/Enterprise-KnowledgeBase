package com.realityrag.retrieval.support;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.profiles.FileProjectionRetrievalProfileStore;
import com.realityrag.retrieval.profiles.RetrievalProfileStore;
import com.realityrag.retrieval.toc.DocumentTocSource;
import com.realityrag.retrieval.toc.FileProjectionDocumentTocSource;
import java.nio.file.Path;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

@TestConfiguration
public class ProfileAndTocFixtureTestConfig {
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

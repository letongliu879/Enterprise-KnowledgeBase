package com.realityrag.retrieval.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "retrieval.data")
public class RetrievalDataProperties {
    private String publishedDocumentsFile;
    private String indexRegistryFile;
    private String retrievalProfilesFile;
    private String indexedChunksFile;
    private String documentTocFile;

    public String getPublishedDocumentsFile() {
        return publishedDocumentsFile;
    }

    public void setPublishedDocumentsFile(String publishedDocumentsFile) {
        this.publishedDocumentsFile = publishedDocumentsFile;
    }

    public String getIndexRegistryFile() {
        return indexRegistryFile;
    }

    public void setIndexRegistryFile(String indexRegistryFile) {
        this.indexRegistryFile = indexRegistryFile;
    }

    public String getRetrievalProfilesFile() {
        return retrievalProfilesFile;
    }

    public void setRetrievalProfilesFile(String retrievalProfilesFile) {
        this.retrievalProfilesFile = retrievalProfilesFile;
    }

    public String getIndexedChunksFile() {
        return indexedChunksFile;
    }

    public void setIndexedChunksFile(String indexedChunksFile) {
        this.indexedChunksFile = indexedChunksFile;
    }

    public String getDocumentTocFile() {
        return documentTocFile;
    }

    public void setDocumentTocFile(String documentTocFile) {
        this.documentTocFile = documentTocFile;
    }
}

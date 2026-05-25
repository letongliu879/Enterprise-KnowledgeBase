package com.realityrag.retrieval.toc;

import java.util.List;

public class InMemoryDocumentTocSource implements DocumentTocSource {
    @Override
    public List<DocumentTocNode> listByDocument(String collectionId, String finalDocId) {
        return List.of();
    }
}

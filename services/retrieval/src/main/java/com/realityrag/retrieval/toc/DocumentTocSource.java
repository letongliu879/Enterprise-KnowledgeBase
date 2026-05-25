package com.realityrag.retrieval.toc;

import java.util.List;

public interface DocumentTocSource {
    List<DocumentTocNode> listByDocument(String collectionId, String finalDocId);
}

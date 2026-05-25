package com.realityrag.retrieval.scope.sources;

import java.util.List;

public interface PublishedDocumentSource {
    List<PublishedDocumentRecord> listByCollection(String collectionId);
}

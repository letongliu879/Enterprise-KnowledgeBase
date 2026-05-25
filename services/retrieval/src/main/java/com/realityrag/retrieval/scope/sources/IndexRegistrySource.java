package com.realityrag.retrieval.scope.sources;

import java.util.Optional;

public interface IndexRegistrySource {
    Optional<IndexRegistryRecord> findActiveIndex(String collectionId);
}

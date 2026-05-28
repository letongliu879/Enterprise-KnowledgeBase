package com.realityrag.retrieval.store;

import java.util.List;

public interface KnowledgeStore {
    List<IndexedChunk> listChunks(String collectionId);

    default List<IndexedChunk> listChunks(String collectionId, String indexVersionId) {
        return listChunks(collectionId).stream()
            .filter(chunk -> indexVersionId == null || indexVersionId.isBlank() || indexVersionId.equals(chunk.indexVersionId()))
            .toList();
    }
}

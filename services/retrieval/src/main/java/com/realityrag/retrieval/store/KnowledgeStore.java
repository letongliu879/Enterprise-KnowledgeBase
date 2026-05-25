package com.realityrag.retrieval.store;

import java.util.List;

public interface KnowledgeStore {
    List<IndexedChunk> listChunks(String collectionId);
}

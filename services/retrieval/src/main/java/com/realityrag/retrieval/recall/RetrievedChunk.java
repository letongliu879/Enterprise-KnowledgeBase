package com.realityrag.retrieval.recall;

import com.realityrag.retrieval.store.IndexedChunk;

public record RetrievedChunk(
    IndexedChunk chunk,
    double score,
    String sourceStage,
    String whySelected
) {}

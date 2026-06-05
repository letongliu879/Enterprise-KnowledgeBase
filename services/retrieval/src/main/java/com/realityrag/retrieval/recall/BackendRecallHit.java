package com.realityrag.retrieval.recall;

import com.realityrag.retrieval.store.IndexedChunk;

public record BackendRecallHit(
    IndexedChunk chunk,
    double score,
    String backendName,
    String whySelected
) {}

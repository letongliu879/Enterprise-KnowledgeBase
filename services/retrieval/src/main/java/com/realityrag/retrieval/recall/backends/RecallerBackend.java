package com.realityrag.retrieval.recall.backends;

import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.store.IndexedChunk;
import java.util.List;

public interface RecallerBackend {
    List<BackendRecallHit> recall(CollectionRetrievalPlan plan, List<IndexedChunk> chunks, String queryText);
}

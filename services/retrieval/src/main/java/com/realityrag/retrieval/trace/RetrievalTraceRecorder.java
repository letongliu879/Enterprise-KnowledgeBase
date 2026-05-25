package com.realityrag.retrieval.trace;

import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.recall.RetrievedChunk;
import java.util.List;

public interface RetrievalTraceRecorder {
    String record(RetrieveRequest request, List<CollectionRetrievalPlan> plans, List<RetrievedChunk> chunks);

    void recordFailure(RetrieveRequest request, List<CollectionRetrievalPlan> plans, Exception error);
}

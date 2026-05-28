package com.realityrag.retrieval.api;

import com.realityrag.retrieval.contracts.KnowledgeContext;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.service.RetrievalService;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.store.KnowledgeStore;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class InternalRetrieveController {
    private final RetrievalService retrievalService;
    private final KnowledgeStore knowledgeStore;

    public InternalRetrieveController(RetrievalService retrievalService, KnowledgeStore knowledgeStore) {
        this.retrievalService = retrievalService;
        this.knowledgeStore = knowledgeStore;
    }

    @PostMapping("/internal/retrieve")
    public KnowledgeContext retrieve(@Valid @RequestBody RetrieveRequest request) {
        System.out.println("[RETRIEVAL_CTRL] /internal/retrieve query_id=" + request.queryId() + " trace_id=" + request.traceId() + " principal=" + request.principal().principalId() + " groups=" + request.principal().groups() + " collection_scope=" + request.collectionScope() + " profile=" + request.retrievalProfileId() + " query=" + request.queryText());
        KnowledgeContext response = retrievalService.retrieve(request);
        System.out.println("[RETRIEVAL_CTRL] /internal/retrieve result_count=" + response.resultChunks().size());
        return response;
    }
}

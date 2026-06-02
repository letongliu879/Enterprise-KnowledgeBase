package com.realityrag.retrieval.api;

import com.realityrag.retrieval.contracts.KnowledgeContext;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.service.RetrievalService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class InternalRetrieveController {
    private static final Logger LOG = LoggerFactory.getLogger(InternalRetrieveController.class);

    private final RetrievalService retrievalService;

    public InternalRetrieveController(RetrievalService retrievalService) {
        this.retrievalService = retrievalService;
    }

    @PostMapping("/internal/retrieve")
    public KnowledgeContext retrieve(@Valid @RequestBody RetrieveRequest request) {
        LOG.info("POST /internal/retrieve queryId={} traceId={} principal={} collections={} profile={}",
            request.queryId(), request.traceId(), request.principal().principalId(),
            request.collectionScope(), request.retrievalProfileId());
        KnowledgeContext response = retrievalService.retrieve(request);
        LOG.info("POST /internal/retrieve resultCount={}", response.resultChunks().size());
        return response;
    }
}

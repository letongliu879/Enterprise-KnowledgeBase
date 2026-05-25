package com.realityrag.retrieval.api;

import com.realityrag.retrieval.contracts.KnowledgeContext;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.service.RetrievalService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class InternalRetrieveController {
    private final RetrievalService retrievalService;

    public InternalRetrieveController(RetrievalService retrievalService) {
        this.retrievalService = retrievalService;
    }

    @PostMapping("/internal/retrieve")
    public KnowledgeContext retrieve(@Valid @RequestBody RetrieveRequest request) {
        return retrievalService.retrieve(request);
    }
}

package com.realityrag.access.api;

import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.service.AccessGatewayService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RetrieveController {
    private final AccessGatewayService accessGatewayService;

    public RetrieveController(AccessGatewayService accessGatewayService) {
        this.accessGatewayService = accessGatewayService;
    }

    @PostMapping("/v1/retrieve")
    public KnowledgeContext retrieve(
        @Valid @RequestBody ExternalRetrieveRequest request,
        HttpServletRequest httpRequest
    ) {
        return accessGatewayService.retrieve(request, httpRequest);
    }
}

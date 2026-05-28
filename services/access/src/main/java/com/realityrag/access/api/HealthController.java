package com.realityrag.access.api;

import com.realityrag.access.clients.RetrievalClient;
import com.realityrag.access.contracts.AccessHealthResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {
    private final RetrievalClient retrievalClient;

    public HealthController(RetrievalClient retrievalClient) {
        this.retrievalClient = retrievalClient;
    }

    @GetMapping("/health")
    public AccessHealthResponse health() {
        String retrievalStatus = retrievalClient.healthStatus();
        String status = retrievalStatus.equals("ok") ? "ok" : "degraded";
        return new AccessHealthResponse("access", status, retrievalStatus);
    }
}

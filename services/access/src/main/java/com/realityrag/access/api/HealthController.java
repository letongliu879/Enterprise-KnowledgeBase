package com.realityrag.access.api;

import com.realityrag.access.contracts.AccessHealthResponse;
import com.realityrag.access.health.RetrievalHealthProbe;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {
    private final RetrievalHealthProbe retrievalHealthProbe;

    public HealthController(RetrievalHealthProbe retrievalHealthProbe) {
        this.retrievalHealthProbe = retrievalHealthProbe;
    }

    @GetMapping("/health")
    public AccessHealthResponse health() {
        String retrievalStatus = retrievalHealthProbe.probe();
        String status = retrievalStatus.equals("ok") ? "ok" : "degraded";
        return new AccessHealthResponse("access", status, retrievalStatus);
    }
}

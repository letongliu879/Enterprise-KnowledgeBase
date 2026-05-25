package com.realityrag.access.health;

import com.realityrag.access.clients.RetrievalClient;
import org.springframework.stereotype.Component;

@Component
public class HttpRetrievalHealthProbe implements RetrievalHealthProbe {
    private final RetrievalClient retrievalClient;

    public HttpRetrievalHealthProbe(RetrievalClient retrievalClient) {
        this.retrievalClient = retrievalClient;
    }

    @Override
    public String probe() {
        return retrievalClient.healthStatus();
    }
}

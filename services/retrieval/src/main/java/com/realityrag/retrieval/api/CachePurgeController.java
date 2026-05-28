package com.realityrag.retrieval.api;

import com.realityrag.retrieval.cache.RetrievalCache;
import com.realityrag.retrieval.cache.RetrievalCacheProperties;
import com.realityrag.retrieval.contracts.CachePurgeRequest;
import com.realityrag.retrieval.contracts.CachePurgeResponse;
import jakarta.validation.Valid;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class CachePurgeController {

    private final RetrievalCache cache;
    private final RetrievalCacheProperties properties;

    public CachePurgeController(RetrievalCache cache, RetrievalCacheProperties properties) {
        this.cache = cache;
        this.properties = properties;
    }

    @PostMapping("/internal/cache/purge")
    public CachePurgeResponse purge(@Valid @RequestBody CachePurgeRequest request) {
        String pattern = properties.getKeyPrefix() + ":*";
        long purged = cache.deleteByPattern(pattern);

        Map<String, Object> scope = new LinkedHashMap<>();
        scope.put("tenant_id", request.tenantId());
        if (request.collectionId() != null) {
            scope.put("collection_id", request.collectionId());
        }
        if (request.docId() != null) {
            scope.put("doc_id", request.docId());
        }
        if (request.evidenceId() != null) {
            scope.put("evidence_id", request.evidenceId());
        }
        return new CachePurgeResponse(purged, scope);
    }
}

package com.realityrag.access.service;

import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.contracts.InternalPrincipal;
import com.realityrag.access.contracts.InternalRetrieveRequest;
import com.realityrag.access.security.AccessRequestContext;
import com.realityrag.access.support.AccessException;
import java.util.LinkedHashSet;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class RetrieveRequestBuilder {
    public InternalRetrieveRequest build(
        ExternalRetrieveRequest request,
        AccessRequestContext context,
        String retrievalProfileId,
        String debugLevel,
        String queryId,
        String traceId
    ) {
        List<String> collectionScope = request.collectionScope().stream()
            .map(String::trim)
            .filter(item -> !item.isBlank())
            .collect(java.util.stream.Collectors.collectingAndThen(
                java.util.stream.Collectors.toCollection(LinkedHashSet::new),
                List::copyOf));
        List<String> forbiddenScopes = collectionScope.stream()
            .filter(scope -> !context.knowledgeScopes().contains(scope))
            .toList();
        if (!forbiddenScopes.isEmpty()) {
            throw new AccessException.Forbidden("Collection scope is not allowed for this API key: " + forbiddenScopes);
        }

        return new InternalRetrieveRequest(
            queryId,
            traceId,
            new InternalPrincipal(
                context.agentTypeId() + ":" + context.agentInstanceId(),
                context.roles(),
                context.knowledgeScopes(),
                context.attributes()
            ),
            collectionScope,
            request.query().trim(),
            request.language(),
            request.crossLanguages(),
            request.keyword(),
            request.metaDataFilter(),
            retrievalProfileId,
            request.filters(),
            false,
            request.maxContextTokens() == null ? context.maxContextTokens() : request.maxContextTokens(),
            debugLevel
        );
    }
}

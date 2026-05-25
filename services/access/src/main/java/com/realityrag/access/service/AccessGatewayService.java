package com.realityrag.access.service;

import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.profiles.RetrievalProfileSelector;
import com.realityrag.access.security.AccessAuthenticator;
import com.realityrag.access.security.AccessRequestContext;
import com.realityrag.access.security.DebugPolicy;
import com.realityrag.access.security.RateLimitGuard;
import com.realityrag.access.trace.AccessTraceRecorder;
import com.realityrag.access.trace.QueryIdentityGenerator;
import com.realityrag.access.translate.AccessResponseMapper;
import com.realityrag.access.translate.RetrieveRequestBuilder;
import com.realityrag.access.clients.RetrievalClient;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.stereotype.Service;

@Service
public class AccessGatewayService {
    private final AccessAuthenticator accessAuthenticator;
    private final DebugPolicy debugPolicy;
    private final RateLimitGuard rateLimitGuard;
    private final RetrievalProfileSelector retrievalProfileSelector;
    private final QueryIdentityGenerator queryIdentityGenerator;
    private final RetrieveRequestBuilder retrieveRequestBuilder;
    private final RetrievalClient retrievalClient;
    private final AccessResponseMapper responseMapper;
    private final AccessTraceRecorder traceRecorder;

    public AccessGatewayService(
        AccessAuthenticator accessAuthenticator,
        DebugPolicy debugPolicy,
        RateLimitGuard rateLimitGuard,
        RetrievalProfileSelector retrievalProfileSelector,
        QueryIdentityGenerator queryIdentityGenerator,
        RetrieveRequestBuilder retrieveRequestBuilder,
        RetrievalClient retrievalClient,
        AccessResponseMapper responseMapper,
        AccessTraceRecorder traceRecorder
    ) {
        this.accessAuthenticator = accessAuthenticator;
        this.debugPolicy = debugPolicy;
        this.rateLimitGuard = rateLimitGuard;
        this.retrievalProfileSelector = retrievalProfileSelector;
        this.queryIdentityGenerator = queryIdentityGenerator;
        this.retrieveRequestBuilder = retrieveRequestBuilder;
        this.retrievalClient = retrievalClient;
        this.responseMapper = responseMapper;
        this.traceRecorder = traceRecorder;
    }

    public KnowledgeContext retrieve(ExternalRetrieveRequest request, HttpServletRequest httpRequest) {
        var accessContext = accessAuthenticator.authenticate(httpRequest);
        return retrieveWithContext(request, accessContext);
    }

    public KnowledgeContext retrieveWithContext(ExternalRetrieveRequest request, AccessRequestContext accessContext) {
        var identity = queryIdentityGenerator.next();
        try {
            traceRecorder.recordRequestAccepted(identity.queryId(), identity.traceId(), accessContext);
            rateLimitGuard.check(accessContext);
            traceRecorder.recordRateLimitChecked(identity.queryId(), identity.traceId(), accessContext);
            String debugLevel = debugPolicy.resolve(request.debug(), accessContext);
            String retrievalProfileId = retrievalProfileSelector.select(request);
            var internalRequest = retrieveRequestBuilder.build(
                request,
                accessContext,
                retrievalProfileId,
                debugLevel,
                identity.queryId(),
                identity.traceId()
            );
            traceRecorder.recordRetrievalCall(internalRequest);
            KnowledgeContext response = retrievalClient.retrieve(internalRequest);
            traceRecorder.recordResponse(identity.queryId(), identity.traceId(), response);
            return responseMapper.map(response);
        }
        catch (RuntimeException error) {
            traceRecorder.recordFailure(identity.queryId(), identity.traceId(), accessContext, error);
            throw error;
        }
    }
}

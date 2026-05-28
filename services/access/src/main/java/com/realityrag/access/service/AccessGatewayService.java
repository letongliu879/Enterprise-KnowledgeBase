package com.realityrag.access.service;

import com.realityrag.access.clients.RetrievalClient;
import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.security.AccessAuthenticator;
import com.realityrag.access.security.AccessRequestContext;
import com.realityrag.access.security.DebugPolicy;
import com.realityrag.access.trace.DefaultQueryIdentityGenerator;
import com.realityrag.access.trace.LoggingAccessTraceRecorder;
import jakarta.servlet.http.HttpServletRequest;
import java.io.FileWriter;
import java.io.IOException;
import java.time.Instant;
import org.springframework.stereotype.Service;

@Service
public class AccessGatewayService {
    private final AccessAuthenticator accessAuthenticator;
    private final DebugPolicy debugPolicy;
    private final RetrievalProfileSelector retrievalProfileSelector;
    private final DefaultQueryIdentityGenerator queryIdentityGenerator;
    private final RetrieveRequestBuilder retrieveRequestBuilder;
    private final RetrievalClient retrievalClient;
    private final LoggingAccessTraceRecorder traceRecorder;

    public AccessGatewayService(
        AccessAuthenticator accessAuthenticator,
        DebugPolicy debugPolicy,
        RetrievalProfileSelector retrievalProfileSelector,
        DefaultQueryIdentityGenerator queryIdentityGenerator,
        RetrieveRequestBuilder retrieveRequestBuilder,
        RetrievalClient retrievalClient,
        LoggingAccessTraceRecorder traceRecorder
    ) {
        this.accessAuthenticator = accessAuthenticator;
        this.debugPolicy = debugPolicy;
        this.retrievalProfileSelector = retrievalProfileSelector;
        this.queryIdentityGenerator = queryIdentityGenerator;
        this.retrieveRequestBuilder = retrieveRequestBuilder;
        this.retrievalClient = retrievalClient;
        this.traceRecorder = traceRecorder;
    }

    private void dbg(String msg) {
        String path = System.getProperty("java.io.tmpdir") + "/access-svc-dbg.log";
        try (FileWriter fw = new FileWriter(path, true)) {
            fw.write(Instant.now() + " " + msg + "\n");
        } catch (IOException ignored) {}
    }

    public KnowledgeContext retrieve(ExternalRetrieveRequest request, HttpServletRequest httpRequest) {
        dbg("[SVC] retrieve() called");
        var accessContext = accessAuthenticator.authenticate(httpRequest);
        dbg("[SVC] authenticate() succeeded api_key_id=" + accessContext.apiKeyId());
        return retrieveWithContext(request, accessContext);
    }

    public KnowledgeContext retrieveWithContext(ExternalRetrieveRequest request, AccessRequestContext accessContext) {
        var identity = queryIdentityGenerator.next();
        dbg("[SVC] retrieveWithContext() query_id=" + identity.queryId());
        try {
            traceRecorder.recordRequestAccepted(identity.queryId(), identity.traceId(), accessContext);
            dbg("[SVC] recordRequestAccepted() done");
            String debugLevel = debugPolicy.resolve(request.debug(), accessContext);
            dbg("[SVC] debugLevel=" + debugLevel);
            String retrievalProfileId = retrievalProfileSelector.select(request);
            dbg("[SVC] retrievalProfileId=" + retrievalProfileId);
            var internalRequest = retrieveRequestBuilder.build(
                request,
                accessContext,
                retrievalProfileId,
                debugLevel,
                identity.queryId(),
                identity.traceId()
            );
            dbg("[SVC] internalRequest built profile=" + internalRequest.retrievalProfileId());
            traceRecorder.recordRetrievalCall(internalRequest);
            dbg("[SVC] recordRetrievalCall() done");
            KnowledgeContext response = retrievalClient.retrieve(internalRequest);
            dbg("[SVC] retrievalClient.retrieve() returned evidence=" + (response == null ? "null" : response.resultChunks().size()));
            traceRecorder.recordResponse(identity.queryId(), identity.traceId(), response);
            return response;
        }
        catch (RuntimeException error) {
            dbg("[SVC] EXCEPTION: " + error.getClass().getName() + " " + error.getMessage());
            traceRecorder.recordFailure(identity.queryId(), identity.traceId(), accessContext, error);
            throw error;
        }
    }
}

package com.realityrag.access.service;

import com.realityrag.access.clients.RetrievalClient;
import com.realityrag.access.config.AccessProperties;
import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.contracts.InternalPrincipal;
import com.realityrag.access.contracts.InternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.security.AccessAuthenticator;
import com.realityrag.access.security.AccessRequestContext;
import com.realityrag.access.support.AccessException;
import com.realityrag.access.trace.LoggingAccessTraceRecorder;
import jakarta.servlet.http.HttpServletRequest;
import java.io.FileWriter;
import java.io.IOException;
import java.time.Instant;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class AccessGatewayService {
    private final AccessAuthenticator accessAuthenticator;
    private final AccessProperties accessProperties;
    private final RetrievalClient retrievalClient;
    private final LoggingAccessTraceRecorder traceRecorder;

    public AccessGatewayService(
        AccessAuthenticator accessAuthenticator,
        AccessProperties accessProperties,
        RetrievalClient retrievalClient,
        LoggingAccessTraceRecorder traceRecorder
    ) {
        this.accessAuthenticator = accessAuthenticator;
        this.accessProperties = accessProperties;
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
        String queryId = "qry_" + UUID.randomUUID();
        String traceId = "trc_" + UUID.randomUUID();
        dbg("[SVC] retrieveWithContext() query_id=" + queryId);
        try {
            traceRecorder.recordRequestAccepted(queryId, traceId, accessContext);
            dbg("[SVC] recordRequestAccepted() done");
            String debugLevel = resolveDebugLevel(request.debug(), accessContext);
            dbg("[SVC] debugLevel=" + debugLevel);
            String retrievalProfileId = selectRetrievalProfile(request);
            dbg("[SVC] retrievalProfileId=" + retrievalProfileId);
            var internalRequest = buildInternalRequest(
                request,
                accessContext,
                retrievalProfileId,
                debugLevel,
                queryId,
                traceId
            );
            dbg("[SVC] internalRequest built profile=" + internalRequest.retrievalProfileId());
            traceRecorder.recordRetrievalCall(internalRequest);
            dbg("[SVC] recordRetrievalCall() done");
            KnowledgeContext response = retrievalClient.retrieve(internalRequest);
            dbg("[SVC] retrievalClient.retrieve() returned evidence=" + (response == null ? "null" : response.resultChunks().size()));
            traceRecorder.recordResponse(queryId, traceId, response);
            return response;
        }
        catch (RuntimeException error) {
            dbg("[SVC] EXCEPTION: " + error.getClass().getName() + " " + error.getMessage());
            traceRecorder.recordFailure(queryId, traceId, accessContext, error);
            throw error;
        }
    }

    private String resolveDebugLevel(String requestedLevel, AccessRequestContext context) {
        String normalized = requestedLevel == null || requestedLevel.isBlank() ? "none" : requestedLevel;
        if (!normalized.equals("none") && !normalized.equals("basic") && !normalized.equals("full")) {
            throw new AccessException.InvalidRequest("Unsupported debug level: " + normalized);
        }
        if (normalized.equals("none")) {
            return "none";
        }
        if (normalized.equals("basic")) {
            return context.debugPermission() ? "basic" : "none";
        }
        if (!context.debugPermission()) {
            throw new AccessException.Forbidden("Full debug is not allowed for this agent integration");
        }
        return "full";
    }

    private String selectRetrievalProfile(ExternalRetrieveRequest request) {
        String explicit = normalize(request.retrievalProfileId());
        String alias = normalize(request.profile());
        if (explicit != null && alias != null && !explicit.equals(alias)) {
            throw new AccessException.InvalidRequest("retrieval_profile_id conflicts with deprecated profile alias");
        }
        if (explicit != null) {
            return requireExisting(explicit);
        }
        if (alias != null) {
            return requireExisting(alias);
        }
        return requireExisting(accessProperties.getDefaultRetrievalProfileId());
    }

    private String normalize(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    private String requireExisting(String profileId) {
        if (!retrievalClient.retrievalProfileExists(profileId)) {
            throw new AccessException.InvalidRequest("Unknown retrieval profile: " + profileId);
        }
        return profileId;
    }

    private InternalRetrieveRequest buildInternalRequest(
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

package com.realityrag.access.clients;

import com.realityrag.access.contracts.InternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.support.AccessException;
import java.io.FileWriter;
import java.io.IOException;
import java.net.SocketTimeoutException;
import java.time.Instant;
import java.util.Map;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

@Component
public class RetrievalClient {
    private final RestClient restClient;

    public RetrievalClient(@Qualifier("retrievalRestClient") RestClient restClient) {
        this.restClient = restClient;
    }

    private void dbg(String msg) {
        String path = System.getProperty("java.io.tmpdir") + "/access-retrieval-dbg.log";
        try (FileWriter fw = new FileWriter(path, true)) {
            fw.write(Instant.now() + " " + msg + "\n");
        } catch (IOException ignored) {}
    }

    public KnowledgeContext retrieve(InternalRetrieveRequest request) {
        dbg("[RETRIEVAL_CLIENT] ENTER retrieve query_id=" + request.queryId());
        try {
            dbg("[RETRIEVAL_CLIENT] Calling /internal/retrieve with query_id=" + request.queryId() + " trace_id=" + request.traceId() + " principal=" + (request.principal() == null ? "null" : request.principal().principalId()) + " collection_scope=" + request.collectionScope() + " profile=" + request.retrievalProfileId());
            KnowledgeContext response = restClient.post()
                .uri("/internal/retrieve")
                .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .header("X-Trace-Id", request.traceId())
                .header("X-Query-Id", request.queryId())
                .body(request)
                .retrieve()
                .body(KnowledgeContext.class);
            dbg("[RETRIEVAL_CLIENT] Response result_count=" + (response == null ? "null" : response.resultChunks().size()));
            return response;
        } catch (RestClientResponseException error) {
            if (error.getStatusCode().value() == 408 || error.getStatusCode().value() == 504) {
                throw new AccessException.RetrievalTimeout("Timed out calling retrieval service", error);
            }
            throw new AccessException.RetrievalUnavailable(
                "Retrieval service returned " + error.getStatusCode().value(),
                error
            );
        } catch (ResourceAccessException error) {
            if (error.getCause() instanceof SocketTimeoutException) {
                throw new AccessException.RetrievalTimeout("Timed out calling retrieval service", error);
            }
            throw new AccessException.RetrievalUnavailable("Failed to call retrieval service", error);
        } catch (Exception error) {
            dbg("[RETRIEVAL_CLIENT] UNEXPECTED EXCEPTION: " + error.getClass().getName() + " " + error.getMessage());
            throw error;
        }
    }

    public String healthStatus() {
        dbg("[RETRIEVAL_CLIENT] healthStatus() called");
        try {
            Map<String, String> response = restClient.get()
                .uri("/health")
                .retrieve()
                .body(Map.class);
            if (response == null) {
                return "unavailable";
            }
            return response.getOrDefault("status", "unknown");
        } catch (RuntimeException error) {
            return "unavailable";
        }
    }

    public boolean retrievalProfileExists(String profileId) {
        dbg("[RETRIEVAL_CLIENT] retrievalProfileExists(" + profileId + ") called");
        try {
            restClient.get()
                .uri("/internal/retrieval-profiles/{profileId}", profileId)
                .retrieve()
                .onStatus(HttpStatusCode::is4xxClientError, (request, response) -> {
                    throw new AccessException.RetrievalUnavailable("Retrieval profile not found", null);
                })
                .toBodilessEntity();
            return true;
        } catch (AccessException.RetrievalUnavailable error) {
            return false;
        } catch (RestClientResponseException error) {
            if (error.getStatusCode().is4xxClientError()) {
                return false;
            }
            throw new AccessException.RetrievalUnavailable(
                "Failed to verify retrieval profile: " + profileId,
                error
            );
        } catch (ResourceAccessException error) {
            throw new AccessException.RetrievalUnavailable(
                "Failed to verify retrieval profile: " + profileId,
                error
            );
        }
    }
}

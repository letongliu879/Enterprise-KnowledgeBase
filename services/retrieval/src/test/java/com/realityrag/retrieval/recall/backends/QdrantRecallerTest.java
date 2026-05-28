package com.realityrag.retrieval.recall.backends;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.embedding.QueryEmbeddingClient;
import com.realityrag.retrieval.store.IndexedChunk;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.function.Executable;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

class QdrantRecallerTest {

    private RetrievalBackendProperties properties;
    private QueryEmbeddingClient embeddingClient;
    private ObjectMapper objectMapper;
    private QdrantRecaller recaller;
    private RestTemplate restTemplate;
    private CollectionRetrievalPlan plan;
    private List<IndexedChunk> chunks;

    @BeforeEach
    void setUp() throws Exception {
        properties = new RetrievalBackendProperties();
        embeddingClient = mock(QueryEmbeddingClient.class);
        objectMapper = new ObjectMapper();
        restTemplate = mock(RestTemplate.class);
        recaller = new QdrantRecaller(properties, embeddingClient, objectMapper);
        var field = QdrantRecaller.class.getDeclaredField("restTemplate");
        field.setAccessible(true);
        field.set(recaller, restTemplate);

        plan = stubPlan();
        chunks = List.of(stubChunk("chk_1", "smoke test content for reimbursement policy"));

        when(embeddingClient.embed(anyString(), anyString()))
            .thenReturn(List.of(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8,
                0.9, 1.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6));
    }

    @Test
    void normalModeFallsBackToStubWhenLiveDisabled() {
        properties.setLiveRecallEnabled(false);
        List<BackendRecallHit> hits = recaller.recall(plan, chunks, "smoke test");
        assertFalse(hits.isEmpty());
        assertTrue(hits.get(0).backendName().contains("stub"));
    }

    @Test
    void normalModeFallsBackToStubWhenLiveFails() {
        properties.setLiveRecallEnabled(true);
        properties.setQdrantBaseUrl("http://127.0.0.1:6333");
        when(restTemplate.exchange(anyString(), eq(HttpMethod.POST), any(), eq(String.class)))
            .thenThrow(new RestClientException("connection refused"));

        List<BackendRecallHit> hits = recaller.recall(plan, chunks, "smoke test");
        assertFalse(hits.isEmpty());
        assertTrue(hits.get(0).backendName().contains("stub"));
    }

    @Test
    void strictModeThrowsWhenLiveDisabled() {
        properties.setLiveRecallEnabled(false);
        properties.setRequireLiveBackends(true);

        Executable action = () -> recaller.recall(plan, chunks, "smoke test");
        IllegalStateException ex = assertThrows(IllegalStateException.class, action);
        assertTrue(ex.getMessage().contains("not configured"));
    }

    @Test
    void strictModeThrowsWhenLiveFails() {
        properties.setLiveRecallEnabled(true);
        properties.setQdrantBaseUrl("http://127.0.0.1:6333");
        properties.setRequireLiveBackends(true);
        when(restTemplate.exchange(anyString(), eq(HttpMethod.POST), any(), eq(String.class)))
            .thenThrow(new RestClientException("connection refused"));

        Executable action = () -> recaller.recall(plan, chunks, "smoke test");
        IllegalStateException ex = assertThrows(IllegalStateException.class, action);
        assertTrue(ex.getMessage().contains("required but failed"));
    }

    @Test
    void strictModeThrowsWhenLiveReturnsEmpty() {
        properties.setLiveRecallEnabled(true);
        properties.setQdrantBaseUrl("http://127.0.0.1:6333");
        properties.setRequireLiveBackends(true);

        String emptyResponse = "{\"result\":{\"points\":[]}}";
        when(restTemplate.exchange(anyString(), eq(HttpMethod.POST), any(), eq(String.class)))
            .thenReturn(ResponseEntity.ok(emptyResponse));

        Executable action = () -> recaller.recall(plan, chunks, "smoke test");
        IllegalStateException ex = assertThrows(IllegalStateException.class, action);
        assertTrue(ex.getMessage().contains("empty results"));
    }

    @Test
    void liveRecallReturnsHits() {
        properties.setLiveRecallEnabled(true);
        properties.setQdrantBaseUrl("http://127.0.0.1:6333");

        String response = "{\"result\":[{\"score\":0.95,"
            + "\"payload\":{\"chunk_id\":\"chk_1\",\"collection_id\":\"col_smoke\","
            + "\"final_doc_id\":\"doc_1\",\"index_version_id\":\"idxv_1\","
            + "\"display_text\":\"test\",\"vector_text\":\"test\","
            + "\"section_path\":[],\"page_spans\":[],"
            + "\"published_document_state\":\"active\",\"visibility\":\"internal\","
            + "\"allowed_principal_ids\":[],\"allowed_groups\":[],"
            + "\"citation_payload\":{},\"metadata\":{}}}]}";
        when(restTemplate.exchange(anyString(), eq(HttpMethod.POST), any(), eq(String.class)))
            .thenReturn(ResponseEntity.ok(response));

        List<BackendRecallHit> hits = recaller.recall(plan, chunks, "smoke test");
        assertFalse(hits.isEmpty());
        assertTrue(hits.get(0).backendName().contains("qdrant_dense"));
        assertFalse(hits.get(0).backendName().contains("stub"));
    }

    private static CollectionRetrievalPlan stubPlan() {
        Map<String, Object> snapshot = new LinkedHashMap<>();
        snapshot.put("candidate_top_k", 20);
        return new CollectionRetrievalPlan(
            "tnt_default", "col_smoke", "idxv_col_smoke_active",
            "os-col-smoke-idxv-col-smoke-active",
            "qd-col-smoke-idxv-col-smoke-active",
            "BAAI/bge-m3", "chunk_smoke", snapshot,
            "ret_smoke_01", 1, "smoke_hash",
            Map.of(), Map.of(), false,
            List.of(), Map.of()
        );
    }

    private static IndexedChunk stubChunk(String chunkId, String displayText) {
        return new IndexedChunk(
            "col_smoke", "doc_1", "idxv_1", "dir_1",
            chunkId, displayText, displayText,
            List.of(), List.of(), "active", "internal",
            List.of(), List.of(), Map.of(), Map.of()
        );
    }
}

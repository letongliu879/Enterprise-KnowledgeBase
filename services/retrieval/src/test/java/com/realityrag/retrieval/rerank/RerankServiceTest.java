package com.realityrag.retrieval.rerank;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import com.realityrag.retrieval.config.RetrievalSearchStrategyProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.recall.RetrievedChunk;
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

class RerankServiceTest {

    private RetrievalSearchStrategyProperties strategyProperties;
    private RetrievalBackendProperties backendProperties;
    private ObjectMapper objectMapper;
    private RerankService rerankService;
    private RestTemplate restTemplate;
    private CollectionRetrievalPlan plan;
    private List<RetrievedChunk> candidates;

    @BeforeEach
    void setUp() throws Exception {
        strategyProperties = new RetrievalSearchStrategyProperties();
        strategyProperties.setEnableRerank(true);
        strategyProperties.setRerankTopN(10);
        strategyProperties.setFusedTopM(60);
        strategyProperties.setEnableRagflowRerankWindow(true);
        strategyProperties.setRagflowRerankWindowMin(30);
        strategyProperties.setRagflowRerankWindowMax(64);
        strategyProperties.setEnableRagflowTokenWeighting(true);
        strategyProperties.setRagflowTitleTokenWeight(2);
        strategyProperties.setRagflowImportantKeywordWeight(5);
        strategyProperties.setRagflowQuestionTokenWeight(6);
        strategyProperties.setEnableRagflowRankFeatures(true);
        strategyProperties.setMaxRerankChars(1000);
        strategyProperties.setMaxBreadcrumbChars(250);
        strategyProperties.setHeadRatio(0.67);

        backendProperties = new RetrievalBackendProperties();
        objectMapper = new ObjectMapper();
        restTemplate = mock(RestTemplate.class);
        rerankService = new RerankService(strategyProperties, backendProperties, objectMapper);
        var field = RerankService.class.getDeclaredField("restTemplate");
        field.setAccessible(true);
        field.set(rerankService, restTemplate);

        plan = liveRerankPlan();
        IndexedChunk chunk = stubChunk("chk_1", "smoke test content for reimbursement policy");
        candidates = List.of(new RetrievedChunk(chunk, 0.85, "hybrid_fusion:opensearch_bm25+qdrant_dense",
            "Matched lexical terms"));
    }

    @Test
    void normalModeFallsBackToHeuristicWhenLiveDisabled() {
        backendProperties.setLiveRerankEnabled(false);
        List<RetrievedChunk> result = rerankService.rerank("smoke test", List.of(plan), candidates);
        assertFalse(result.isEmpty());
        assertTrue(result.get(0).sourceStage().contains("rerank_heuristic"));
    }

    @Test
    void normalModeFallsBackToHeuristicWhenLiveFails() {
        backendProperties.setLiveRerankEnabled(true);
        backendProperties.setRerankerBaseUrl("https://api.siliconflow.cn/v1/rerank");
        backendProperties.setRerankerApiKey("sk-test-key");
        backendProperties.setRerankerModel("BAAI/bge-reranker-v2-m3");
        when(restTemplate.exchange(anyString(), eq(HttpMethod.POST), any(), eq(String.class)))
            .thenThrow(new RestClientException("connection refused"));

        List<RetrievedChunk> result = rerankService.rerank("smoke test", List.of(plan), candidates);
        assertFalse(result.isEmpty());
        assertTrue(result.get(0).sourceStage().contains("rerank_heuristic"));
    }

    @Test
    void strictModeThrowsWhenLiveUnavailable() {
        backendProperties.setLiveRerankEnabled(false);
        backendProperties.setRequireLiveBackends(true);

        Executable action = () -> rerankService.rerank("smoke test", List.of(plan), candidates);
        IllegalStateException ex = assertThrows(IllegalStateException.class, action);
        assertTrue(ex.getMessage().contains("not configured"));
    }

    @Test
    void strictModeThrowsWhenLiveFails() {
        backendProperties.setLiveRerankEnabled(true);
        backendProperties.setRerankerBaseUrl("https://api.siliconflow.cn/v1/rerank");
        backendProperties.setRerankerApiKey("sk-test-key");
        backendProperties.setRerankerModel("BAAI/bge-reranker-v2-m3");
        backendProperties.setRequireLiveBackends(true);
        when(restTemplate.exchange(anyString(), eq(HttpMethod.POST), any(), eq(String.class)))
            .thenThrow(new RestClientException("connection refused"));

        Executable action = () -> rerankService.rerank("smoke test", List.of(plan), candidates);
        IllegalStateException ex = assertThrows(IllegalStateException.class, action);
        assertTrue(ex.getMessage().contains("required but failed"));
    }

    @Test
    void rerankDisabledInProfileDoesNotCrash() {
        backendProperties.setLiveRerankEnabled(true);
        backendProperties.setRerankerBaseUrl("https://api.siliconflow.cn/v1/rerank");
        backendProperties.setRerankerApiKey("sk-test-key");
        backendProperties.setRerankerModel("BAAI/bge-reranker-v2-m3");

        CollectionRetrievalPlan rerankDisabledPlan = rerankDisabledPlan();
        List<RetrievedChunk> result = rerankService.rerank("smoke test", List.of(rerankDisabledPlan), candidates);
        assertFalse(result.isEmpty());
    }

    @Test
    void strictModeWithLiveRerankReturnsLiveResults() {
        backendProperties.setLiveRerankEnabled(true);
        backendProperties.setRerankerBaseUrl("https://api.siliconflow.cn/v1/rerank");
        backendProperties.setRerankerApiKey("sk-test-key");
        backendProperties.setRerankerModel("BAAI/bge-reranker-v2-m3");
        backendProperties.setRequireLiveBackends(true);

        String response = "{\"results\":[{\"index\":0,\"relevance_score\":0.92}]}";
        when(restTemplate.exchange(anyString(), eq(HttpMethod.POST), any(), eq(String.class)))
            .thenReturn(ResponseEntity.ok(response));

        List<RetrievedChunk> result = rerankService.rerank("smoke test", List.of(plan), candidates);
        assertFalse(result.isEmpty());
        assertTrue(result.get(0).sourceStage().contains("rerank_live"));
    }

    private static CollectionRetrievalPlan liveRerankPlan() {
        Map<String, Object> snapshot = new LinkedHashMap<>();
        snapshot.put("candidate_top_k", 20);
        snapshot.put("rerank_enabled", true);
        snapshot.put("rerank_model", "BAAI/bge-reranker-v2-m3");
        snapshot.put("bm25_weight", 0.3);
        snapshot.put("vector_weight", 0.7);
        return new CollectionRetrievalPlan(
            "tnt_default", "col_smoke", "idxv_col_smoke_active",
            "os-col-smoke", "qd-col-smoke",
            "BAAI/bge-m3", "chunk_smoke", snapshot,
            "ret_smoke_01", 1, "smoke_hash",
            Map.of(), Map.of(), false,
            List.of(), Map.of()
        );
    }

    private static CollectionRetrievalPlan rerankDisabledPlan() {
        Map<String, Object> snapshot = new LinkedHashMap<>();
        snapshot.put("candidate_top_k", 20);
        snapshot.put("rerank_enabled", false);
        snapshot.put("rerank_model", "none");
        snapshot.put("bm25_weight", 0.3);
        snapshot.put("vector_weight", 0.7);
        return new CollectionRetrievalPlan(
            "tnt_default", "col_smoke", "idxv_col_smoke_active",
            "os-col-smoke", "qd-col-smoke",
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
            List.of("Section 1"), List.of(), "active", "internal",
            List.of(), List.of(), Map.of(), Map.of()
        );
    }
}

package com.realityrag.retrieval.recall.backends;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.embedding.QueryEmbeddingClient;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.support.RetrievalUtils;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class QdrantRecaller implements RecallerBackend {
    private static final Logger LOG = LoggerFactory.getLogger(QdrantRecaller.class);

    private final RetrievalBackendProperties backendProperties;
    private final QueryEmbeddingClient queryEmbeddingClient;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public QdrantRecaller(
        RetrievalBackendProperties backendProperties,
        QueryEmbeddingClient queryEmbeddingClient,
        ObjectMapper objectMapper
    ) {
        this.backendProperties = backendProperties;
        this.queryEmbeddingClient = queryEmbeddingClient;
        this.restTemplate = new RestTemplate();
        this.objectMapper = objectMapper;
    }

    @Override
    public List<BackendRecallHit> recall(CollectionRetrievalPlan plan, List<IndexedChunk> chunks, String queryText) {
        boolean liveConfigured = backendProperties.isLiveRecallEnabled()
            && hasBaseUrl(backendProperties.getQdrantBaseUrl());

        if (liveConfigured) {
            try {
                List<BackendRecallHit> hits = recallLive(plan, queryText);
                if (!hits.isEmpty()) {
                    LOG.info("Qdrant live recall returned {} hits for collection={}", hits.size(), plan.collectionId());
                    return hits;
                }
                LOG.warn("Qdrant live recall returned empty results for collection={}", plan.collectionId());
                if (backendProperties.isRequireLiveBackends()) {
                    throw new IllegalStateException(
                        "Qdrant live recall required but returned empty results for collection=" + plan.collectionId());
                }
            } catch (IllegalStateException strictError) {
                throw strictError;
            } catch (RuntimeException error) {
                LOG.warn("Qdrant live recall failed: {} — falling back to stub", error.getMessage());
                if (backendProperties.isRequireLiveBackends()) {
                    throw new IllegalStateException(
                        "Qdrant live recall required but failed: " + error.getMessage(), error);
                }
            }
        } else {
            if (backendProperties.isRequireLiveBackends()) {
                throw new IllegalStateException(
                    "Qdrant live recall required but not configured (live-recall-enabled="
                    + backendProperties.isLiveRecallEnabled()
                    + ", qdrant-base-url=" + backendProperties.getQdrantBaseUrl() + ")");
            }
            LOG.debug("Qdrant using stub recall for collection={}", plan.collectionId());
        }

        return recallStub(chunks, queryText);
    }

    List<BackendRecallHit> recallStub(List<IndexedChunk> chunks, String queryText) {
        String normalizedQuery = RetrievalUtils.normalizeQuery(queryText);
        String[] queryTerms = normalizedQuery.split("\\s+");
        List<BackendRecallHit> hits = new ArrayList<>();
        for (IndexedChunk chunk : chunks) {
            double score = denseScore(queryTerms, chunk.vectorText());
            if (score <= 0.0d) {
                continue;
            }
            hits.add(new BackendRecallHit(
                chunk,
                score,
                "qdrant_dense_stub",
                "Matched semantic/vector text terms."
            ));
        }
        return hits;
    }

    List<BackendRecallHit> recallLive(CollectionRetrievalPlan plan, String queryText) {
        String url = backendProperties.getQdrantBaseUrl().replaceAll("/+$", "")
            + "/collections/" + plan.qdrantCollection() + "/points/search";
        Map<String, Object> payload = new java.util.LinkedHashMap<>();
        payload.put("vector", queryEmbeddingClient.embed(queryText, plan.embeddingModel()));
        payload.put("limit", candidateTopK(plan));
        payload.put("with_payload", true);
        if (!plan.allowedDocIds().isEmpty()) {
            payload.put("filter", Map.of(
                "must", List.of(
                    Map.of("key", "final_doc_id", "match", Map.of("any", plan.allowedDocIds()))
                )
            ));
        }
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);
        ResponseEntity<String> response = restTemplate.exchange(url, HttpMethod.POST, request, String.class);
        return parseQdrantHits(response.getBody() == null ? "" : response.getBody());
    }

    private List<BackendRecallHit> parseQdrantHits(String body) {
        try {
            JsonNode root = objectMapper.readTree(body);
            JsonNode rawResult = root.path("result");
            List<JsonNode> points = new ArrayList<>();
            if (rawResult.isArray()) {
                rawResult.forEach(points::add);
            } else if (rawResult.isObject() && rawResult.path("points").isArray()) {
                rawResult.path("points").forEach(points::add);
            }
            List<BackendRecallHit> hits = new ArrayList<>();
            for (JsonNode point : points) {
                JsonNode payload = point.path("payload");
                String chunkId = payload.path("chunk_id").asText("");
                if (chunkId.isBlank()) {
                    continue;
                }
                IndexedChunk chunk = toIndexedChunk(payload);
                double rawScore = point.path("score").asDouble(0.0d);
                hits.add(new BackendRecallHit(
                    chunk,
                    RetrievalUtils.normalizeBackendScore(rawScore),
                    "qdrant_dense",
                    "Matched dense vector recall in Qdrant."
                ));
            }
            return hits;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to parse Qdrant response", error);
        }
    }

    private double denseScore(String[] queryTerms, String haystack) {
        String loweredHaystack = haystack.toLowerCase(Locale.ROOT);
        double matched = 0.0d;
        for (String term : queryTerms) {
            if (term.isBlank()) {
                continue;
            }
            if (loweredHaystack.contains(term)) {
                matched += 0.75d;
            }
        }
        return matched == 0.0d ? 0.0d : matched / Math.max(1, queryTerms.length);
    }

    private IndexedChunk toIndexedChunk(JsonNode payload) {
        return new IndexedChunk(
            payload.path("collection_id").asText(""),
            payload.path("final_doc_id").asText(""),
            payload.path("index_version_id").asText(""),
            payload.path("document_index_revision_id").asText(""),
            payload.path("chunk_id").asText(""),
            payload.path("display_text").asText(""),
            payload.path("vector_text").asText(""),
            RetrievalUtils.jsonTextList(payload.path("section_path")),
            RetrievalUtils.jsonPageSpans(payload.path("page_spans")),
            payload.path("published_document_state").asText(""),
            payload.path("visibility").asText(""),
            RetrievalUtils.jsonTextList(payload.path("allowed_principal_ids")),
            RetrievalUtils.jsonTextList(payload.path("allowed_groups")),
            objectMapper.convertValue(payload.path("citation_payload"), Map.class),
            objectMapper.convertValue(payload.path("metadata"), Map.class)
        );
    }

    private int candidateTopK(CollectionRetrievalPlan plan) {
        Object value = plan.retrievalProfileSnapshot().get("candidate_top_k");
        return value instanceof Number number ? number.intValue() : 20;
    }

    private boolean hasBaseUrl(String value) {
        return value != null && !value.isBlank();
    }
}

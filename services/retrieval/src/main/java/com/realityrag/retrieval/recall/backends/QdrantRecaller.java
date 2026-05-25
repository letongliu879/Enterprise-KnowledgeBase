package com.realityrag.retrieval.recall.backends;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.embedding.QueryEmbeddingClient;
import com.realityrag.retrieval.store.IndexedChunk;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class QdrantRecaller implements RecallerBackend {
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
        if (backendProperties.isLiveRecallEnabled() && hasBaseUrl(backendProperties.getQdrantBaseUrl())) {
            try {
                List<BackendRecallHit> hits = recallLive(plan, queryText);
                if (!hits.isEmpty()) {
                    return hits;
                }
            } catch (RuntimeException error) {
                // Fall back to stub scoring until live infrastructure is available everywhere.
            }
        }
        return recallStub(chunks, queryText);
    }

    List<BackendRecallHit> recallStub(List<IndexedChunk> chunks, String queryText) {
        String normalizedQuery = normalizeQuery(queryText);
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
                    normalizeBackendScore(rawScore),
                    "qdrant_dense",
                    "Matched dense vector recall in Qdrant."
                ));
            }
            return hits;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to parse Qdrant response", error);
        }
    }

    private String normalizeQuery(String queryText) {
        return queryText.toLowerCase(Locale.ROOT).replaceAll("[^\\p{IsAlphabetic}\\p{IsDigit}\\s]+", " ");
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

    private double normalizeBackendScore(double rawScore) {
        if (rawScore <= 0.0d) {
            return 0.0d;
        }
        return Math.max(0.0d, Math.min(1.0d, 1 - Math.exp(-rawScore)));
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
            jsonTextList(payload.path("section_path")),
            jsonPageSpans(payload.path("page_spans")),
            payload.path("published_document_state").asText(""),
            payload.path("visibility").asText(""),
            jsonTextList(payload.path("allowed_principal_ids")),
            jsonTextList(payload.path("allowed_groups")),
            objectMapper.convertValue(payload.path("citation_payload"), Map.class),
            objectMapper.convertValue(payload.path("metadata"), Map.class)
        );
    }

    private List<String> jsonTextList(JsonNode node) {
        if (!node.isArray()) {
            return List.of();
        }
        List<String> values = new ArrayList<>();
        node.forEach(item -> values.add(item.asText()));
        return values;
    }

    private List<com.realityrag.retrieval.contracts.KnowledgeContext.PageSpan> jsonPageSpans(JsonNode node) {
        if (!node.isArray()) {
            return List.of();
        }
        List<com.realityrag.retrieval.contracts.KnowledgeContext.PageSpan> spans = new ArrayList<>();
        for (JsonNode item : node) {
            spans.add(new com.realityrag.retrieval.contracts.KnowledgeContext.PageSpan(
                item.path("page_from").asInt(1),
                item.path("page_to").asInt(1)
            ));
        }
        return spans;
    }

    private boolean hasBaseUrl(String value) {
        return value != null && !value.isBlank();
    }

    private int candidateTopK(CollectionRetrievalPlan plan) {
        Object value = plan.retrievalProfileSnapshot().get("candidate_top_k");
        return value instanceof Number number ? number.intValue() : 20;
    }
}

package com.realityrag.retrieval.recall;

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
import java.util.Objects;
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
public class HybridRecaller {
    private static final Logger LOG = LoggerFactory.getLogger(HybridRecaller.class);

    private final RetrievalBackendProperties backendProperties;
    private final QueryEmbeddingClient queryEmbeddingClient;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public HybridRecaller(
        RetrievalBackendProperties backendProperties,
        QueryEmbeddingClient queryEmbeddingClient,
        ObjectMapper objectMapper
    ) {
        this.backendProperties = backendProperties;
        this.queryEmbeddingClient = queryEmbeddingClient;
        this.restTemplate = new RestTemplate();
        this.objectMapper = objectMapper;
    }

    public List<BackendRecallHit> recallLexical(CollectionRetrievalPlan plan, List<IndexedChunk> chunks, String queryText) {
        boolean liveConfigured = backendProperties.isLiveRecallEnabled()
            && hasBaseUrl(backendProperties.getOpensearchBaseUrl());

        if (liveConfigured) {
            try {
                List<BackendRecallHit> hits = recallLexicalLive(plan, queryText);
                if (!hits.isEmpty()) {
                    LOG.info("OpenSearch live recall returned {} hits for collection={}", hits.size(), plan.collectionId());
                    return hits;
                }
                LOG.warn("OpenSearch live recall returned empty results for collection={}", plan.collectionId());
                if (backendProperties.isRequireLiveBackends()) {
                    throw new IllegalStateException(
                        "OpenSearch live recall required but returned empty results for collection=" + plan.collectionId());
                }
            } catch (IllegalStateException strictError) {
                throw strictError;
            } catch (RuntimeException error) {
                LOG.warn("OpenSearch live recall failed: {} — falling back to stub", error.getMessage());
                if (backendProperties.isRequireLiveBackends()) {
                    throw new IllegalStateException(
                        "OpenSearch live recall required but failed: " + error.getMessage(), error);
                }
            }
        } else {
            if (backendProperties.isRequireLiveBackends()) {
                throw new IllegalStateException(
                    "OpenSearch live recall required but not configured (live-recall-enabled="
                    + backendProperties.isLiveRecallEnabled()
                    + ", opensearch-base-url=" + backendProperties.getOpensearchBaseUrl() + ")");
            }
            LOG.debug("OpenSearch using stub recall for collection={}", plan.collectionId());
        }

        return recallLexicalStub(chunks, queryText);
    }

    public List<BackendRecallHit> recallVector(CollectionRetrievalPlan plan, List<IndexedChunk> chunks, String queryText) {
        boolean liveConfigured = backendProperties.isLiveRecallEnabled()
            && hasBaseUrl(backendProperties.getQdrantBaseUrl());

        if (liveConfigured) {
            try {
                List<BackendRecallHit> hits = recallVectorLive(plan, queryText);
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

        return recallVectorStub(chunks, queryText);
    }

    // ---- Lexical (OpenSearch) ----

    private List<BackendRecallHit> recallLexicalStub(List<IndexedChunk> chunks, String queryText) {
        String normalizedQuery = normalizeQuery(queryText);
        String[] queryTerms = normalizedQuery.split("\\s+");
        List<BackendRecallHit> hits = new ArrayList<>();
        for (IndexedChunk chunk : chunks) {
            double score = lexicalScore(queryTerms, chunk.displayText());
            if (score <= 0.0d) {
                continue;
            }
            hits.add(new BackendRecallHit(
                chunk,
                score,
                "opensearch_bm25_stub",
                "Matched lexical terms in display text."
            ));
        }
        return hits;
    }

    private List<BackendRecallHit> recallLexicalLive(CollectionRetrievalPlan plan, String queryText) {
        String url = backendProperties.getOpensearchBaseUrl().replaceAll("/+$", "") + "/" + plan.opensearchIndex() + "/_search";
        Map<String, Object> payload = Map.of(
            "size", candidateTopK(plan),
            "query", Map.of(
                "bool", Map.of(
                    "must", List.of(Map.of("match", Map.of("display_text", queryText))),
                    "filter", buildFilters(plan)
                )
            )
        );
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);
        ResponseEntity<String> response = restTemplate.exchange(url, HttpMethod.POST, request, String.class);
        return parseOpenSearchHits(Objects.requireNonNullElse(response.getBody(), ""));
    }

    private List<BackendRecallHit> parseOpenSearchHits(String body) {
        try {
            JsonNode root = objectMapper.readTree(body);
            List<BackendRecallHit> hits = new ArrayList<>();
            for (JsonNode hit : root.path("hits").path("hits")) {
                JsonNode source = hit.path("_source");
                String chunkId = source.path("chunk_id").asText("");
                if (chunkId.isBlank()) {
                    continue;
                }
                IndexedChunk chunk = toIndexedChunk(source);
                double rawScore = hit.path("_score").asDouble(0.0d);
                hits.add(new BackendRecallHit(
                    chunk,
                    normalizeScore(rawScore),
                    "opensearch_bm25",
                    "Matched lexical terms in OpenSearch."
                ));
            }
            return hits;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to parse OpenSearch response", error);
        }
    }

    // ---- Vector (Qdrant) ----

    private List<BackendRecallHit> recallVectorStub(List<IndexedChunk> chunks, String queryText) {
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

    private List<BackendRecallHit> recallVectorLive(CollectionRetrievalPlan plan, String queryText) {
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
                    normalizeScore(rawScore),
                    "qdrant_dense",
                    "Matched dense vector recall in Qdrant."
                ));
            }
            return hits;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to parse Qdrant response", error);
        }
    }

    // ---- Shared helpers ----

    private IndexedChunk toIndexedChunk(JsonNode source) {
        return new IndexedChunk(
            source.path("collection_id").asText(""),
            source.path("final_doc_id").asText(""),
            source.path("index_version_id").asText(""),
            source.path("document_index_revision_id").asText(""),
            source.path("chunk_id").asText(""),
            source.path("display_text").asText(""),
            source.path("vector_text").asText(""),
            jsonTextList(source.path("section_path")),
            jsonPageSpans(source.path("page_spans")),
            source.path("published_document_state").asText(""),
            source.path("visibility").asText(""),
            jsonTextList(source.path("allowed_principal_ids")),
            jsonTextList(source.path("allowed_groups")),
            objectMapper.convertValue(source.path("citation_payload"), Map.class),
            objectMapper.convertValue(source.path("metadata"), Map.class)
        );
    }

    private List<Map<String, Object>> buildFilters(CollectionRetrievalPlan plan) {
        List<Map<String, Object>> filters = new ArrayList<>();
        if (!plan.allowedDocIds().isEmpty()) {
            filters.add(Map.of("terms", Map.of("final_doc_id", plan.allowedDocIds())));
        }
        Object visibility = plan.metadataFilters().get("visibility");
        if (visibility != null) {
            filters.add(Map.of("term", Map.of("visibility", visibility)));
        }
        return filters;
    }

    private double lexicalScore(String[] queryTerms, String haystack) {
        String loweredHaystack = haystack.toLowerCase(Locale.ROOT);
        double matched = 0.0d;
        for (String term : queryTerms) {
            if (term.isBlank()) {
                continue;
            }
            if (loweredHaystack.contains(term)) {
                matched += 1.0d;
            }
        }
        return matched == 0.0d ? 0.0d : matched / Math.max(1, queryTerms.length);
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

    private static String normalizeQuery(String queryText) {
        if (queryText == null || queryText.isBlank()) {
            return "";
        }
        return queryText.toLowerCase(Locale.ROOT).replaceAll("[^\\p{IsAlphabetic}\\p{IsDigit}\\s]+", " ").trim();
    }

    private static double normalizeScore(double raw) {
        return Math.max(0.0d, Math.min(1.0d, raw));
    }

    @SuppressWarnings("unchecked")
    private static List<String> jsonTextList(JsonNode node) {
        if (!node.isArray()) {
            return List.of();
        }
        List<String> result = new ArrayList<>();
        node.forEach(child -> result.add(child.asText("")));
        return result;
    }

    @SuppressWarnings("unchecked")
    private static List<com.realityrag.retrieval.contracts.KnowledgeContext.PageSpan> jsonPageSpans(JsonNode node) {
        if (!node.isArray()) {
            return List.of();
        }
        List<com.realityrag.retrieval.contracts.KnowledgeContext.PageSpan> result = new ArrayList<>();
        node.forEach(child -> {
            int from = child.path("page_from").asInt(1);
            int to = child.path("page_to").asInt(1);
            result.add(new com.realityrag.retrieval.contracts.KnowledgeContext.PageSpan(from, to));
        });
        return result;
    }

    private int candidateTopK(CollectionRetrievalPlan plan) {
        Object value = plan.retrievalProfileSnapshot().get("candidate_top_k");
        return value instanceof Number number ? number.intValue() : 20;
    }

    private boolean hasBaseUrl(String value) {
        return value != null && !value.isBlank();
    }
}

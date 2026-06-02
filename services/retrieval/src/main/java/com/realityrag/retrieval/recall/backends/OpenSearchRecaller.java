package com.realityrag.retrieval.recall.backends;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.support.RetrievalUtils;
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
public class OpenSearchRecaller implements RecallerBackend {
    private static final Logger LOG = LoggerFactory.getLogger(OpenSearchRecaller.class);

    private final RetrievalBackendProperties backendProperties;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public OpenSearchRecaller(
        RetrievalBackendProperties backendProperties,
        ObjectMapper objectMapper
    ) {
        this.backendProperties = backendProperties;
        this.restTemplate = new RestTemplate();
        this.objectMapper = objectMapper;
    }

    @Override
    public List<BackendRecallHit> recall(CollectionRetrievalPlan plan, List<IndexedChunk> chunks, String queryText) {
        boolean liveConfigured = backendProperties.isLiveRecallEnabled()
            && hasBaseUrl(backendProperties.getOpensearchBaseUrl());

        if (liveConfigured) {
            try {
                List<BackendRecallHit> hits = recallLive(plan, queryText);
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

        return recallStub(chunks, queryText);
    }

    List<BackendRecallHit> recallStub(List<IndexedChunk> chunks, String queryText) {
        String normalizedQuery = RetrievalUtils.normalizeQuery(queryText);
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

    List<BackendRecallHit> recallLive(CollectionRetrievalPlan plan, String queryText) {
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
                    RetrievalUtils.normalizeBackendScore(rawScore),
                    "opensearch_bm25",
                    "Matched lexical terms in OpenSearch."
                ));
            }
            return hits;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to parse OpenSearch response", error);
        }
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

    private IndexedChunk toIndexedChunk(JsonNode source) {
        return new IndexedChunk(
            source.path("collection_id").asText(""),
            source.path("final_doc_id").asText(""),
            source.path("index_version_id").asText(""),
            source.path("document_index_revision_id").asText(""),
            source.path("chunk_id").asText(""),
            source.path("display_text").asText(""),
            source.path("vector_text").asText(""),
            RetrievalUtils.jsonTextList(source.path("section_path")),
            RetrievalUtils.jsonPageSpans(source.path("page_spans")),
            source.path("published_document_state").asText(""),
            source.path("visibility").asText(""),
            RetrievalUtils.jsonTextList(source.path("allowed_principal_ids")),
            RetrievalUtils.jsonTextList(source.path("allowed_groups")),
            objectMapper.convertValue(source.path("citation_payload"), Map.class),
            objectMapper.convertValue(source.path("metadata"), Map.class)
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

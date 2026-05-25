package com.realityrag.retrieval.recall.backends;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.store.IndexedChunk;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

@Component
public class OpenSearchRecaller implements RecallerBackend {
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
        if (backendProperties.isLiveRecallEnabled() && hasBaseUrl(backendProperties.getOpensearchBaseUrl())) {
            try {
                List<BackendRecallHit> hits = recallLive(plan, queryText);
                if (!hits.isEmpty()) {
                    return hits;
                }
            } catch (RuntimeException error) {
                // Fall back to stub scoring until the backend is fully wired in every environment.
            }
        }
        return recallStub(chunks, queryText);
    }

    List<BackendRecallHit> recallStub(List<IndexedChunk> chunks, String queryText) {
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
                    normalizeBackendScore(rawScore),
                    "opensearch_bm25",
                    "Matched lexical terms in OpenSearch."
                ));
            }
            return hits;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to parse OpenSearch response", error);
        }
    }

    private String normalizeQuery(String queryText) {
        return queryText.toLowerCase(Locale.ROOT).replaceAll("[^\\p{IsAlphabetic}\\p{IsDigit}\\s]+", " ");
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

    private double normalizeBackendScore(double rawScore) {
        if (rawScore <= 0.0d) {
            return 0.0d;
        }
        return Math.max(0.0d, Math.min(1.0d, 1 - Math.exp(-rawScore)));
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

    private List<String> jsonTextList(JsonNode node) {
        if (!node.isArray()) {
            return List.of();
        }
        return asList(node).stream().map(JsonNode::asText).toList();
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

    private List<JsonNode> asList(JsonNode node) {
        List<JsonNode> values = new ArrayList<>();
        node.forEach(values::add);
        return values;
    }

    private boolean hasBaseUrl(String value) {
        return value != null && !value.isBlank();
    }

    private int candidateTopK(CollectionRetrievalPlan plan) {
        Object value = plan.retrievalProfileSnapshot().get("candidate_top_k");
        return value instanceof Number number ? number.intValue() : 20;
    }

}

package com.realityrag.retrieval.cache;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrievalScope;
import com.realityrag.retrieval.recall.RetrievedChunk;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

@Component
public class RetrievalCacheKeyBuilder {
    private static final String QEMB_VERSION = "v1";
    private static final String RECALL_VERSION = "v1";

    private final RetrievalCacheProperties properties;
    private final ObjectMapper objectMapper;

    public RetrievalCacheKeyBuilder(RetrievalCacheProperties properties, ObjectMapper objectMapper) {
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    public String queryEmbeddingKey(String queryText, String embeddingModel, String embeddingClient, String embeddingBaseUrl) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("query_text", queryText == null ? "" : queryText);
        payload.put("embedding_model", embeddingModel == null ? "" : embeddingModel);
        payload.put("embedding_client", embeddingClient == null ? "" : embeddingClient);
        payload.put("embedding_base_url_fingerprint", fingerprintUrl(embeddingBaseUrl));
        String hash = sha256Hex(canonicalJson(payload));
        return buildKey("qemb", QEMB_VERSION, hash);
    }

    public String recallKey(RetrievalScope scope, List<CollectionRetrievalPlan> plans, String queryText, int candidateTopK) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("query_text", queryText == null ? "" : queryText);
        payload.put("principal_id", scope.principalId());
        payload.put("principal_groups", sortedList(extractPrincipalGroups(scope)));
        payload.put("collection_ids", sortedList(plans.stream().map(CollectionRetrievalPlan::collectionId).toList()));

        Map<String, String> activeIndexVersions = new LinkedHashMap<>();
        Map<String, String> profileHashes = new LinkedHashMap<>();
        Map<String, String> embeddingModels = new LinkedHashMap<>();
        for (CollectionRetrievalPlan plan : sortByCollectionId(plans)) {
            activeIndexVersions.put(plan.collectionId(), plan.activeIndexVersionId());
            profileHashes.put(plan.collectionId(), plan.profileHash());
            embeddingModels.put(plan.collectionId(), plan.embeddingModel());
        }
        payload.put("active_index_versions", activeIndexVersions);
        payload.put("profile_hashes", profileHashes);
        payload.put("embedding_models", embeddingModels);

        payload.put("allowed_doc_ids_hash", sha256Hex(canonicalJson(scope.allowedDocIds())));
        payload.put("metadata_filters_hash", sha256Hex(canonicalJson(scope.metadataFilters())));
        payload.put("lifecycle_filter_hash", sha256Hex(canonicalJson(extractLifecycleFilters(plans))));
        payload.put("include_deprecated", scope.includeDeprecated());
        payload.put("candidate_top_k", candidateTopK);

        String opensearchIndex = sortByCollectionId(plans).stream()
            .map(CollectionRetrievalPlan::opensearchIndex)
            .filter(s -> s != null && !s.isBlank())
            .findFirst().orElse("");
        String qdrantCollection = sortByCollectionId(plans).stream()
            .map(CollectionRetrievalPlan::qdrantCollection)
            .filter(s -> s != null && !s.isBlank())
            .findFirst().orElse("");
        payload.put("opensearch_index", opensearchIndex);
        payload.put("qdrant_collection", qdrantCollection);

        String hash = sha256Hex(canonicalJson(payload));
        return buildKey("recall", RECALL_VERSION, hash);
    }

    private String buildKey(String namespace, String version, String hash) {
        String prefix = properties.getKeyPrefix();
        return prefix + ":" + namespace + ":" + version + ":" + hash;
    }

    private String canonicalJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception error) {
            throw new IllegalStateException("Failed to serialize cache key payload", error);
        }
    }

    private static String sha256Hex(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException("SHA-256 not available", error);
        }
    }

    private static String fingerprintUrl(String url) {
        if (url == null || url.isBlank()) {
            return "";
        }
        String normalized = url.replaceAll("/+$", "").toLowerCase();
        return sha256Hex(normalized).substring(0, 16);
    }

    @SuppressWarnings("unchecked")
    private static List<String> extractPrincipalGroups(RetrievalScope scope) {
        Object groups = scope.metadataFilters().get("principal_groups");
        if (groups instanceof List<?> list) {
            return list.stream().map(Object::toString).toList();
        }
        return List.of();
    }

    private static Map<String, Object> extractLifecycleFilters(List<CollectionRetrievalPlan> plans) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (CollectionRetrievalPlan plan : sortByCollectionId(plans)) {
            result.put(plan.collectionId(), plan.lifecycleFilter());
        }
        return result;
    }

    private static List<CollectionRetrievalPlan> sortByCollectionId(List<CollectionRetrievalPlan> plans) {
        return plans.stream()
            .sorted(Comparator.comparing(CollectionRetrievalPlan::collectionId))
            .toList();
    }

    private static List<String> sortedList(List<String> list) {
        return list.stream().sorted().toList();
    }
}

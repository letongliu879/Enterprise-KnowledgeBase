package com.realityrag.retrieval.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.realityrag.retrieval.contracts.RetrievalProfileValidateRequest;
import com.realityrag.retrieval.contracts.RetrievalProfileValidateResponse;
import com.realityrag.retrieval.contracts.RetrievalProfileValidateResponse.ValidationError;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import org.springframework.stereotype.Service;

@Service
public class RetrievalProfileValidator {

    private static final String VALIDATOR_VERSION = "1.0.0";
    private static final String RUNTIME_OWNER = "retrieval";

    private static final Set<String> VALID_RERANK_MODELS = Set.of(
        "default", "none", "bge-reranker-v2-m3", "rerank-v1", "rerank-multilingual-v1.0"
    );

    private static final Set<String> VALID_FAIL_POLICIES = Set.of("fail_open", "fail_closed");

    private static final Set<String> VALID_EXPANSION_TYPES = Set.of("neighbor", "breadcrumb", "none");

    private static final List<String> CANONICAL_KEY_ORDER = List.of(
        "bm25_weight",
        "vector_weight",
        "candidate_top_k",
        "similarity_threshold",
        "rerank_enabled",
        "rerank_model",
        "fail_policy",
        "expansion_policy",
        "pack_budget"
    );

    private final ObjectMapper objectMapper;

    public RetrievalProfileValidator(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper.copy()
            .configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
    }

    public RetrievalProfileValidateResponse validate(RetrievalProfileValidateRequest request) {
        List<String> warnings = new ArrayList<>();
        List<ValidationError> errors = new ArrayList<>();
        Map<String, Object> config = new LinkedHashMap<>(request.profileConfig());

        // 1. Validate weights
        validateWeights(config, errors);

        // 2. Validate candidate_top_k
        validateCandidateTopK(config, errors);

        // 3. Validate pack_budget (token_budget in runtime terms)
        validatePackBudget(config, errors, warnings);

        // 4. Validate rerank_model
        validateRerankModel(config, errors, warnings);

        // 5. Validate expansion_policy
        validateExpansionPolicy(config, errors);

        // 6. Validate fail_policy
        validateFailPolicy(config, errors);

        // 7. Validate similarity_threshold
        validateSimilarityThreshold(config, errors, warnings);

        // 8. Validate rerank_enabled consistency
        validateRerankEnabledConsistency(config, errors, warnings);

        boolean valid = errors.isEmpty();

        Map<String, Object> canonicalConfig = null;
        String profileHash = computePlaceholderHash();

        if (valid) {
            canonicalConfig = buildCanonicalConfig(config);
            profileHash = computeProfileHash(request.retrievalProfileId(), canonicalConfig);
        } else {
            profileHash = computePlaceholderHash();
        }

        return new RetrievalProfileValidateResponse(
            valid,
            canonicalConfig,
            profileHash,
            warnings,
            errors,
            RUNTIME_OWNER,
            VALIDATOR_VERSION
        );
    }

    private void validateWeights(Map<String, Object> config, List<ValidationError> errors) {
        Double bm25 = getDouble(config, "bm25_weight");
        Double vector = getDouble(config, "vector_weight");

        if (bm25 == null) {
            errors.add(new ValidationError("MISSING_BM25_WEIGHT", "bm25_weight is required"));
        } else if (bm25 < 0.0 || bm25 > 1.0) {
            errors.add(new ValidationError("INVALID_BM25_WEIGHT",
                String.format("bm25_weight must be between 0.0 and 1.0, got %.4f", bm25)));
        }

        if (vector == null) {
            errors.add(new ValidationError("MISSING_VECTOR_WEIGHT", "vector_weight is required"));
        } else if (vector < 0.0 || vector > 1.0) {
            errors.add(new ValidationError("INVALID_VECTOR_WEIGHT",
                String.format("vector_weight must be between 0.0 and 1.0, got %.4f", vector)));
        }

        if (bm25 != null && vector != null) {
            double sum = bm25 + vector;
            if (Math.abs(sum - 1.0) > 1e-6) {
                errors.add(new ValidationError("BM25_VECTOR_WEIGHT_SUM",
                    String.format("bm25_weight + vector_weight must equal 1.0, got %.4f", sum)));
            }
        }
    }

    private void validateCandidateTopK(Map<String, Object> config, List<ValidationError> errors) {
        Integer topK = getInteger(config, "candidate_top_k");
        if (topK == null) {
            errors.add(new ValidationError("MISSING_CANDIDATE_TOP_K", "candidate_top_k is required"));
        } else if (topK <= 0) {
            errors.add(new ValidationError("INVALID_CANDIDATE_TOP_K",
                String.format("candidate_top_k must be > 0, got %d", topK)));
        } else if (topK > 1000) {
            errors.add(new ValidationError("CANDIDATE_TOP_K_TOO_LARGE",
                String.format("candidate_top_k must be <= 1000, got %d", topK)));
        }
    }

    private void validatePackBudget(Map<String, Object> config, List<ValidationError> errors,
                                     List<String> warnings) {
        Integer budget = getInteger(config, "pack_budget");
        if (budget == null) {
            errors.add(new ValidationError("MISSING_PACK_BUDGET", "pack_budget is required"));
        } else if (budget <= 0) {
            errors.add(new ValidationError("INVALID_PACK_BUDGET",
                String.format("pack_budget must be > 0, got %d", budget)));
        } else if (budget > 100000) {
            warnings.add(String.format("pack_budget %d is unusually large; may impact packing performance", budget));
        }
    }

    private void validateRerankModel(Map<String, Object> config, List<ValidationError> errors,
                                      List<String> warnings) {
        Object rerankModel = config.get("rerank_model");
        if (rerankModel == null) {
            errors.add(new ValidationError("MISSING_RERANK_MODEL", "rerank_model is required"));
            return;
        }

        String model = rerankModel.toString();
        if (model.isBlank()) {
            errors.add(new ValidationError("EMPTY_RERANK_MODEL", "rerank_model must not be blank"));
            return;
        }

        if (!VALID_RERANK_MODELS.contains(model)) {
            errors.add(new ValidationError("INVALID_RERANK_MODEL",
                String.format("Rerank model '%s' is not available in retrieval runtime", model)));
        }

        if ("none".equals(model)) {
            Object rerankEnabled = config.get("rerank_enabled");
            if (Boolean.TRUE.equals(rerankEnabled)) {
                warnings.add("rerank_model is 'none' but rerank_enabled is true; reranking will be skipped");
            }
        }
    }

    private void validateExpansionPolicy(Map<String, Object> config, List<ValidationError> errors) {
        Object expansion = config.get("expansion_policy");
        if (expansion == null) {
            // expansion_policy is optional; default to empty map
            return;
        }

        if (!(expansion instanceof Map<?, ?>)) {
            errors.add(new ValidationError("INVALID_EXPANSION_POLICY",
                "expansion_policy must be an object"));
            return;
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> policy = (Map<String, Object>) expansion;
        Object type = policy.get("type");
        if (type != null) {
            String typeStr = type.toString();
            if (!VALID_EXPANSION_TYPES.contains(typeStr)) {
                errors.add(new ValidationError("INVALID_EXPANSION_TYPE",
                    String.format("expansion_policy.type must be one of %s, got '%s'", VALID_EXPANSION_TYPES, typeStr)));
            }
        }
    }

    private void validateFailPolicy(Map<String, Object> config, List<ValidationError> errors) {
        Object failPolicy = config.get("fail_policy");
        if (failPolicy == null) {
            errors.add(new ValidationError("MISSING_FAIL_POLICY", "fail_policy is required"));
            return;
        }

        String policy = failPolicy.toString();
        if (!VALID_FAIL_POLICIES.contains(policy)) {
            errors.add(new ValidationError("INVALID_FAIL_POLICY",
                String.format("fail_policy must be one of %s, got '%s'", VALID_FAIL_POLICIES, policy)));
        }
    }

    private void validateSimilarityThreshold(Map<String, Object> config, List<ValidationError> errors,
                                              List<String> warnings) {
        Double threshold = getDouble(config, "similarity_threshold");
        if (threshold == null) {
            errors.add(new ValidationError("MISSING_SIMILARITY_THRESHOLD", "similarity_threshold is required"));
            return;
        }

        if (threshold < 0.0 || threshold > 1.0) {
            errors.add(new ValidationError("INVALID_SIMILARITY_THRESHOLD",
                String.format("similarity_threshold must be between 0.0 and 1.0, got %.4f", threshold)));
        } else if (threshold > 0.9) {
            warnings.add("similarity_threshold above 0.9 may severely reduce recall");
        } else if (threshold < 0.1) {
            warnings.add("similarity_threshold below 0.1 may include too much noise");
        }
    }

    private void validateRerankEnabledConsistency(Map<String, Object> config, List<ValidationError> errors,
                                                   List<String> warnings) {
        Object rerankEnabled = config.get("rerank_enabled");
        Object rerankModel = config.get("rerank_model");

        if (rerankEnabled == null) {
            errors.add(new ValidationError("MISSING_RERANK_ENABLED", "rerank_enabled is required"));
            return;
        }

        if (!(rerankEnabled instanceof Boolean)) {
            errors.add(new ValidationError("INVALID_RERANK_ENABLED",
                "rerank_enabled must be a boolean"));
            return;
        }

        boolean enabled = (Boolean) rerankEnabled;
        if (enabled && rerankModel != null && "none".equals(rerankModel.toString())) {
            warnings.add("rerank_enabled is true but rerank_model is 'none'; no reranking will occur");
        }
    }

    private Map<String, Object> buildCanonicalConfig(Map<String, Object> config) {
        Map<String, Object> canonical = new LinkedHashMap<>();

        for (String key : CANONICAL_KEY_ORDER) {
            if (config.containsKey(key)) {
                canonical.put(key, normalizeValue(config.get(key)));
            } else {
                canonical.put(key, getDefaultValue(key));
            }
        }

        // Remove any extra keys that are not in canonical order
        // (already handled by only iterating CANONICAL_KEY_ORDER)

        return canonical;
    }

    private Object normalizeValue(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> normalized = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                normalized.put(entry.getKey().toString(), normalizeValue(entry.getValue()));
            }
            return normalized;
        }
        if (value instanceof Number number) {
            // Normalize integer-like doubles to integers for cleaner canonical form
            if (number.doubleValue() == number.longValue()) {
                return number.longValue();
            }
            return number.doubleValue();
        }
        return value;
    }

    private Object getDefaultValue(String key) {
        return switch (key) {
            case "bm25_weight" -> 0.5;
            case "vector_weight" -> 0.5;
            case "candidate_top_k" -> 20;
            case "similarity_threshold" -> 0.2;
            case "rerank_enabled" -> true;
            case "rerank_model" -> "default";
            case "fail_policy" -> "fail_closed";
            case "expansion_policy" -> Map.of();
            case "pack_budget" -> 1200;
            default -> null;
        };
    }

    String computeProfileHash(String profileId, Map<String, Object> canonicalConfig) {
        try {
            // Deterministic serialization: TreeMap for key ordering
            Map<String, Object> deterministic = new TreeMap<>(canonicalConfig);
            String json = objectMapper.writeValueAsString(deterministic);
            String payload = profileId + "|" + json;
            return "sha256:" + sha256Hex(payload);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize canonical config for hashing", e);
        }
    }

    private static String computePlaceholderHash() {
        return "sha256:0000000000000000000000000000000000000000000000000000000000000000";
    }

    private static String sha256Hex(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 not available", e);
        }
    }

    private static Double getDouble(Map<String, Object> config, String key) {
        Object value = config.get(key);
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        try {
            return Double.parseDouble(value.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static Integer getInteger(Map<String, Object> config, String key) {
        Object value = config.get(key);
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(value.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }
}

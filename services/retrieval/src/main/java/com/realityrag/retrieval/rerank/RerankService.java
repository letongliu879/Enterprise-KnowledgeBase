package com.realityrag.retrieval.rerank;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalBackendProperties;
import com.realityrag.retrieval.config.RetrievalSearchStrategyProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.recall.RetrievedChunk;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class RerankService {
    private static final Pattern TOKEN_SPLIT_PATTERN = Pattern.compile("[^\\p{IsAlphabetic}\\p{IsDigit}]+");
    private final RetrievalSearchStrategyProperties strategyProperties;
    private final RetrievalBackendProperties backendProperties;
    private final ObjectMapper objectMapper;
    private final RestTemplate restTemplate;

    public RerankService(
        RetrievalSearchStrategyProperties strategyProperties,
        RetrievalBackendProperties backendProperties,
        ObjectMapper objectMapper
    ) {
        this.strategyProperties = strategyProperties;
        this.backendProperties = backendProperties;
        this.objectMapper = objectMapper;
        this.restTemplate = new RestTemplate();
    }

    public List<RetrievedChunk> rerank(
        String queryText,
        List<CollectionRetrievalPlan> plans,
        List<RetrievedChunk> candidates
    ) {
        if (candidates.isEmpty()) {
            return List.of();
        }

        Map<String, CollectionRetrievalPlan> planByCollection = plans.stream()
            .collect(Collectors.toMap(
                CollectionRetrievalPlan::collectionId,
                plan -> plan,
                (left, right) -> left,
                LinkedHashMap::new
            ));

        Set<String> queryTokens = tokenize(queryText);
        Map<String, Double> queryRankFeatures = buildQueryRankFeatures(queryTokens);
        List<RetrievedChunk> reranked = new ArrayList<>();
        Map<String, List<RetrievedChunk>> groupedCandidates = candidates.stream()
            .collect(Collectors.groupingBy(
                item -> item.chunk().collectionId(),
                LinkedHashMap::new,
                Collectors.toList()
            ));

        for (Map.Entry<String, List<RetrievedChunk>> entry : groupedCandidates.entrySet()) {
            CollectionRetrievalPlan plan = planByCollection.get(entry.getKey());
            reranked.addAll(rerankPerCollection(queryText, queryTokens, queryRankFeatures, plan, entry.getValue()));
        }

        return reranked.stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .toList();
    }

    private List<RetrievedChunk> rerankPerCollection(
        String queryText,
        Set<String> queryTokens,
        Map<String, Double> queryRankFeatures,
        CollectionRetrievalPlan plan,
        List<RetrievedChunk> candidates
    ) {
        List<RetrievedChunk> sortedCandidates = candidates.stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .toList();

        if (plan == null || !strategyProperties.isEnableRerank() || !profileRerankEnabled(plan)) {
            return sortedCandidates;
        }

        List<RetrievedChunk> rerankWindow = applyRagflowRerankWindow(plan, sortedCandidates);
        double tokenWeight = resolveTokenWeight(plan);
        double vectorWeight = resolveVectorWeight(plan);
        String rerankModel = resolveRerankModel(plan);

        if (backendProperties.isLiveRerankEnabled()
            && hasText(backendProperties.getRerankerBaseUrl())
            && hasText(backendProperties.getRerankerApiKey())
            && hasText(rerankModel)) {
            try {
                List<RetrievedChunk> liveResults = rerankLive(
                    queryText,
                    queryTokens,
                    queryRankFeatures,
                    rerankWindow,
                    rerankModel,
                    tokenWeight,
                    vectorWeight
                );
                if (!liveResults.isEmpty()) {
                    return liveResults;
                }
            } catch (RuntimeException ignored) {
                // Fall back to local scoring when the live reranker is unavailable.
            }
        }

        return rerankFallback(queryTokens, queryRankFeatures, rerankWindow, tokenWeight, vectorWeight);
    }

    private List<RetrievedChunk> rerankFallback(
        Set<String> queryTokens,
        Map<String, Double> queryRankFeatures,
        List<RetrievedChunk> candidates,
        double tokenWeight,
        double vectorWeight
    ) {
        List<ScoredCandidate> scored = new ArrayList<>();
        for (RetrievedChunk candidate : candidates) {
            WeightedTokenProfile tokenProfile = buildWeightedTokenProfile(candidate);
            double tokenSimilarity = computeTokenSimilarity(queryTokens, tokenProfile);
            double rankFeatureBoost = computeRankFeatureBoost(candidate, queryRankFeatures);
            double finalScore = tokenWeight * tokenSimilarity + vectorWeight * candidate.score() + rankFeatureBoost;
            scored.add(new ScoredCandidate(candidate, clampScore(finalScore), tokenSimilarity, rankFeatureBoost));
        }

        return scored.stream()
            .sorted(Comparator.comparingDouble(ScoredCandidate::score).reversed())
            .limit(strategyProperties.getRerankTopN())
            .map(item -> new RetrievedChunk(
                item.candidate().chunk(),
                item.score(),
                "rerank_heuristic",
                "RAGFlow fallback rerank: token_similarity="
                    + formatScore(item.tokenSimilarity())
                    + ", rank_feature="
                    + formatScore(item.rankFeatureBoost())
            ))
            .toList();
    }

    private List<RetrievedChunk> rerankLive(
        String queryText,
        Set<String> queryTokens,
        Map<String, Double> queryRankFeatures,
        List<RetrievedChunk> candidates,
        String rerankModel,
        double tokenWeight,
        double vectorWeight
    ) {
        List<WeightedTokenProfile> tokenProfiles = candidates.stream()
            .map(this::buildWeightedTokenProfile)
            .toList();
        List<String> documents = tokenProfiles.stream()
            .map(WeightedTokenProfile::rerankDocument)
            .toList();

        String url = backendProperties.getRerankerBaseUrl().replaceAll("/+$", "");
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", rerankModel);
        payload.put("query", queryText);
        payload.put("documents", documents);
        payload.put("top_n", Math.min(strategyProperties.getRerankTopN(), documents.size()));
        payload.put("return_documents", false);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(backendProperties.getRerankerApiKey());
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);
        ResponseEntity<String> response = restTemplate.exchange(url, HttpMethod.POST, request, String.class);

        return parseLiveRerankResponse(
            response.getBody() == null ? "" : response.getBody(),
            candidates,
            tokenProfiles,
            queryTokens,
            queryRankFeatures,
            rerankModel,
            tokenWeight,
            vectorWeight
        );
    }

    private List<RetrievedChunk> parseLiveRerankResponse(
        String body,
        List<RetrievedChunk> candidates,
        List<WeightedTokenProfile> tokenProfiles,
        Set<String> queryTokens,
        Map<String, Double> queryRankFeatures,
        String rerankModel,
        double tokenWeight,
        double vectorWeight
    ) {
        try {
            JsonNode root = objectMapper.readTree(body);
            JsonNode results = root.path("results");
            if (!results.isArray()) {
                return List.of();
            }

            List<RetrievedChunk> reranked = new ArrayList<>();
            for (JsonNode result : results) {
                int originalIndex = result.path("index").asInt(-1);
                if (originalIndex < 0 || originalIndex >= candidates.size()) {
                    continue;
                }
                RetrievedChunk candidate = candidates.get(originalIndex);
                WeightedTokenProfile tokenProfile = tokenProfiles.get(originalIndex);
                double tokenSimilarity = computeTokenSimilarity(queryTokens, tokenProfile);
                double modelScore = clampScore(result.path("relevance_score").asDouble(candidate.score()));
                double rankFeatureBoost = computeRankFeatureBoost(candidate, queryRankFeatures);
                double finalScore = tokenWeight * tokenSimilarity + vectorWeight * modelScore + rankFeatureBoost;
                reranked.add(new RetrievedChunk(
                    candidate.chunk(),
                    clampScore(finalScore),
                    "rerank_live",
                    "RAGFlow live rerank model "
                        + rerankModel
                        + ": token_similarity="
                        + formatScore(tokenSimilarity)
                        + ", model_score="
                        + formatScore(modelScore)
                ));
            }
            return reranked.stream()
                .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
                .toList();
        } catch (IOException error) {
            throw new IllegalStateException("Failed to parse rerank response", error);
        }
    }

    private List<RetrievedChunk> applyRagflowRerankWindow(CollectionRetrievalPlan plan, List<RetrievedChunk> candidates) {
        if (!strategyProperties.isEnableRagflowRerankWindow()) {
            return candidates.stream().limit(strategyProperties.getFusedTopM()).toList();
        }

        int topK = candidateTopK(plan);
        int effectiveWindow = topK <= 0
            ? strategyProperties.getRagflowRerankWindowMin()
            : Math.max(strategyProperties.getRagflowRerankWindowMin(), Math.min(topK, strategyProperties.getRagflowRerankWindowMax()));
        return candidates.stream()
            .limit(Math.min(effectiveWindow, strategyProperties.getFusedTopM()))
            .toList();
    }

    private WeightedTokenProfile buildWeightedTokenProfile(RetrievedChunk candidate) {
        Map<String, Integer> tokenWeights = new LinkedHashMap<>();
        appendTokens(tokenWeights, tokenize(preferredContent(candidate)), 1);

        if (strategyProperties.isEnableRagflowTokenWeighting()) {
            appendTokens(tokenWeights, titleTokens(candidate), strategyProperties.getRagflowTitleTokenWeight());
            appendTokens(tokenWeights, importantKeywordTokens(candidate), strategyProperties.getRagflowImportantKeywordWeight());
            appendTokens(tokenWeights, questionHintTokens(candidate), strategyProperties.getRagflowQuestionTokenWeight());
        }

        String rerankDocument = buildRerankDocument(candidate, tokenWeights);
        int totalWeight = tokenWeights.values().stream().mapToInt(Integer::intValue).sum();
        return new WeightedTokenProfile(tokenWeights, Math.max(1, totalWeight), rerankDocument);
    }

    private String buildRerankDocument(RetrievedChunk candidate, Map<String, Integer> tokenWeights) {
        String breadcrumb = String.join(" > ", candidate.chunk().sectionPath());
        String truncatedBreadcrumb = truncateMiddle(breadcrumb, strategyProperties.getMaxBreadcrumbChars());
        int budget = Math.max(0, strategyProperties.getMaxRerankChars() - truncatedBreadcrumb.length() - 1);
        String snippet = extractAroundHit(candidate.chunk().displayText(), tokenWeights.keySet(), budget);
        if (snippet.isBlank()) {
            snippet = truncateHeadTail(candidate.chunk().displayText(), budget);
        }
        return truncatedBreadcrumb.isBlank() ? snippet : truncatedBreadcrumb + "\n" + snippet;
    }

    private double computeTokenSimilarity(Set<String> queryTokens, WeightedTokenProfile tokenProfile) {
        if (queryTokens.isEmpty()) {
            return 0.0d;
        }
        int matchedWeight = 0;
        for (String token : queryTokens) {
            matchedWeight += tokenProfile.tokenWeights().getOrDefault(token, 0);
        }
        return matchedWeight == 0 ? 0.0d : (double) matchedWeight / tokenProfile.totalWeight();
    }

    private double computeRankFeatureBoost(RetrievedChunk candidate, Map<String, Double> queryRankFeatures) {
        if (!strategyProperties.isEnableRagflowRankFeatures()) {
            return 0.0d;
        }

        double pagerank = numericMetadata(candidate, "pagerank", "pagerank_fea");
        Map<String, Double> tagFeatures = metadataFeatureMap(candidate, "tag_fea", "tag_feas");
        if (tagFeatures.isEmpty() || queryRankFeatures.isEmpty()) {
            return pagerank;
        }

        double queryNorm = 0.0d;
        for (Map.Entry<String, Double> entry : queryRankFeatures.entrySet()) {
            queryNorm += entry.getValue() * entry.getValue();
        }
        queryNorm = Math.sqrt(queryNorm);
        if (queryNorm == 0.0d) {
            return pagerank;
        }

        double numerator = 0.0d;
        double chunkNorm = 0.0d;
        for (Map.Entry<String, Double> entry : tagFeatures.entrySet()) {
            numerator += queryRankFeatures.getOrDefault(entry.getKey(), 0.0d) * entry.getValue();
            chunkNorm += entry.getValue() * entry.getValue();
        }
        if (chunkNorm == 0.0d) {
            return pagerank;
        }

        double tagScore = numerator / (Math.sqrt(chunkNorm) * queryNorm);
        return tagScore * 10.0d + pagerank;
    }

    private Set<String> tokenize(String rawText) {
        if (!hasText(rawText)) {
            return Set.of();
        }
        Set<String> tokens = new LinkedHashSet<>();
        for (String token : TOKEN_SPLIT_PATTERN.split(rawText.toLowerCase(Locale.ROOT))) {
            if (!token.isBlank()) {
                tokens.add(token);
            }
        }
        return tokens;
    }

    private void appendTokens(Map<String, Integer> tokenWeights, Set<String> tokens, int weight) {
        if (weight <= 0) {
            return;
        }
        for (String token : tokens) {
            tokenWeights.merge(token, weight, Integer::sum);
        }
    }

    private Set<String> titleTokens(RetrievedChunk candidate) {
        Set<String> metadataTokens = metadataStringSet(candidate, "title_tks");
        if (!metadataTokens.isEmpty()) {
            return metadataTokens;
        }
        if (!candidate.chunk().sectionPath().isEmpty()) {
            return tokenize(candidate.chunk().sectionPath().get(0));
        }
        return Set.of();
    }

    private Set<String> importantKeywordTokens(RetrievedChunk candidate) {
        Set<String> metadataTokens = metadataStringSet(candidate, "important_kwd");
        if (!metadataTokens.isEmpty()) {
            return metadataTokens;
        }
        return metadataStringSet(candidate, "important_keywords");
    }

    private Set<String> questionHintTokens(RetrievedChunk candidate) {
        return metadataStringSet(candidate, "question_tks");
    }

    private Set<String> metadataStringSet(RetrievedChunk candidate, String key) {
        Object raw = candidate.chunk().metadata().get(key);
        if (raw instanceof List<?> list) {
            return list.stream()
                .map(String::valueOf)
                .flatMap(item -> tokenize(item).stream())
                .collect(Collectors.toCollection(LinkedHashSet::new));
        }
        if (raw instanceof String stringValue) {
            return tokenize(stringValue);
        }
        return Set.of();
    }

    private Map<String, Double> metadataFeatureMap(RetrievedChunk candidate, String... keys) {
        for (String key : keys) {
            Object raw = candidate.chunk().metadata().get(key);
            if (raw instanceof Map<?, ?> mapValue) {
                Map<String, Double> values = new LinkedHashMap<>();
                for (Map.Entry<?, ?> entry : mapValue.entrySet()) {
                    Double parsed = toDouble(entry.getValue());
                    if (parsed != null) {
                        values.put(String.valueOf(entry.getKey()).toLowerCase(Locale.ROOT), parsed);
                    }
                }
                return values;
            }
        }
        return Map.of();
    }

    private double numericMetadata(RetrievedChunk candidate, String... keys) {
        for (String key : keys) {
            Double value = toDouble(candidate.chunk().metadata().get(key));
            if (value != null) {
                return value;
            }
        }
        return 0.0d;
    }

    private Double toDouble(Object raw) {
        if (raw instanceof Number number) {
            return number.doubleValue();
        }
        if (raw instanceof String stringValue && hasText(stringValue)) {
            try {
                return Double.parseDouble(stringValue);
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return null;
    }

    private Map<String, Double> buildQueryRankFeatures(Set<String> queryTokens) {
        Map<String, Double> features = new LinkedHashMap<>();
        for (String token : queryTokens) {
            features.put(token.toLowerCase(Locale.ROOT), 1.0d);
        }
        return features;
    }

    private String preferredContent(RetrievedChunk candidate) {
        if (hasText(candidate.chunk().displayText())) {
            return candidate.chunk().displayText();
        }
        return candidate.chunk().vectorText();
    }

    private int candidateTopK(CollectionRetrievalPlan plan) {
        Object value = plan.retrievalProfileSnapshot().get("candidate_top_k");
        return value instanceof Number number ? number.intValue() : 0;
    }

    private double resolveTokenWeight(CollectionRetrievalPlan plan) {
        Object value = plan.retrievalProfileSnapshot().get("bm25_weight");
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        return 0.3d;
    }

    private double resolveVectorWeight(CollectionRetrievalPlan plan) {
        Object value = plan.retrievalProfileSnapshot().get("vector_weight");
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        return 0.7d;
    }

    private boolean profileRerankEnabled(CollectionRetrievalPlan plan) {
        Object value = plan.retrievalProfileSnapshot().get("rerank_enabled");
        if (value instanceof Boolean bool) {
            return bool;
        }
        if (value instanceof String stringValue) {
            return Boolean.parseBoolean(stringValue);
        }
        return true;
    }

    private String resolveRerankModel(CollectionRetrievalPlan plan) {
        Object value = plan.retrievalProfileSnapshot().get("rerank_model");
        return value == null ? "" : value.toString();
    }

    private String truncateMiddle(String text, int maxLen) {
        if (text == null || text.length() <= maxLen) {
            return text == null ? "" : text;
        }
        int half = Math.max(0, (maxLen - 3) / 2);
        return text.substring(0, half) + "..." + text.substring(text.length() - half);
    }

    private String truncateHeadTail(String text, int maxLen) {
        if (text == null || text.length() <= maxLen) {
            return text == null ? "" : text;
        }
        int headLen = (int) Math.floor(maxLen * strategyProperties.getHeadRatio());
        int tailLen = maxLen - headLen - 3;
        if (tailLen <= 0) {
            return text.substring(0, maxLen);
        }
        return text.substring(0, headLen) + "..." + text.substring(text.length() - tailLen);
    }

    private String extractAroundHit(String text, Set<String> queryTokens, int maxLen) {
        if (text == null || text.isBlank() || maxLen <= 0) {
            return "";
        }
        if (text.length() <= maxLen) {
            return text;
        }

        String[] lines = text.split("\\R");
        int hitLineIndex = -1;
        int bestScore = 0;
        for (int i = 0; i < lines.length; i++) {
            String loweredLine = lines[i].toLowerCase(Locale.ROOT);
            int lineScore = 0;
            for (String token : queryTokens) {
                if (loweredLine.contains(token)) {
                    lineScore++;
                }
            }
            if (lineScore > bestScore) {
                bestScore = lineScore;
                hitLineIndex = i;
            }
        }

        if (hitLineIndex < 0) {
            return truncateHeadTail(text, maxLen);
        }

        int start = hitLineIndex;
        int end = hitLineIndex;
        int currentLength = lines[hitLineIndex].length();
        while (currentLength < maxLen) {
            boolean canUp = start > 0;
            boolean canDown = end < lines.length - 1;
            if (!canUp && !canDown) {
                break;
            }

            if (canUp) {
                int upLength = lines[start - 1].length() + 1;
                if (currentLength + upLength <= maxLen) {
                    start--;
                    currentLength += upLength;
                }
            }
            if (canDown) {
                int downLength = lines[end + 1].length() + 1;
                if (currentLength + downLength <= maxLen) {
                    end++;
                    currentLength += downLength;
                }
            }

            boolean exhaustedUp = start == 0 || currentLength + lines[start - 1].length() + 1 > maxLen;
            boolean exhaustedDown = end == lines.length - 1 || currentLength + lines[end + 1].length() + 1 > maxLen;
            if (exhaustedUp && exhaustedDown) {
                break;
            }
        }

        String result = String.join("\n", java.util.Arrays.copyOfRange(lines, start, end + 1));
        String prefix = start > 0 ? "..." : "";
        String suffix = end < lines.length - 1 ? "..." : "";
        return prefix + result + suffix;
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    private double clampScore(double value) {
        return Math.max(0.0d, Math.min(1.0d, value));
    }

    private String formatScore(double value) {
        return String.format(Locale.ROOT, "%.2f", value);
    }

    private record ScoredCandidate(
        RetrievedChunk candidate,
        double score,
        double tokenSimilarity,
        double rankFeatureBoost
    ) {}

    private record WeightedTokenProfile(
        Map<String, Integer> tokenWeights,
        int totalWeight,
        String rerankDocument
    ) {}
}

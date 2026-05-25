package com.realityrag.retrieval.preprocess;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalSearchStrategyProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.prompt.PromptModelClient;
import com.realityrag.retrieval.prompt.PromptTemplateRepository;
import com.realityrag.retrieval.scope.sources.PublishedDocumentRecord;
import com.realityrag.retrieval.scope.sources.PublishedDocumentSource;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.store.KnowledgeStore;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Component;

@Component
public class MetadataFilterService {
    private final RetrievalSearchStrategyProperties strategyProperties;
    private final KnowledgeStore knowledgeStore;
    private final PublishedDocumentSource publishedDocumentSource;
    private final PromptModelClient promptModelClient;
    private final PromptTemplateRepository promptTemplateRepository;
    private final ObjectMapper objectMapper;

    public MetadataFilterService(
        RetrievalSearchStrategyProperties strategyProperties,
        KnowledgeStore knowledgeStore,
        PublishedDocumentSource publishedDocumentSource,
        PromptModelClient promptModelClient,
        PromptTemplateRepository promptTemplateRepository,
        ObjectMapper objectMapper
    ) {
        this.strategyProperties = strategyProperties;
        this.knowledgeStore = knowledgeStore;
        this.publishedDocumentSource = publishedDocumentSource;
        this.promptModelClient = promptModelClient;
        this.promptTemplateRepository = promptTemplateRepository;
        this.objectMapper = objectMapper;
    }

    public List<String> resolveAllowedDocIds(RetrieveRequest request, List<CollectionRetrievalPlan> plans) {
        Map<String, Object> metadataFilter = request.metaDataFilter();
        if (metadataFilter.isEmpty()) {
            return plans.stream().flatMap(plan -> plan.allowedDocIds().stream()).distinct().toList();
        }

        String method = stringValue(metadataFilter.get("method"));
        if (!strategyProperties.isEnableRagflowMetadataAutoFilter()
            && ("auto".equalsIgnoreCase(method) || "semi_auto".equalsIgnoreCase(method))) {
            return plans.stream().flatMap(plan -> plan.allowedDocIds().stream()).distinct().toList();
        }

        Map<String, Map<String, Set<String>>> metadataIndex = buildMetadataIndex(plans);
        List<String> baseDocIds = plans.stream().flatMap(plan -> plan.allowedDocIds().stream()).distinct().toList();

        return switch (method.toLowerCase(Locale.ROOT)) {
            case "auto" -> applyAutoFilter(metadataIndex, request.queryText(), baseDocIds, Map.of());
            case "semi_auto" -> applySemiAutoFilter(metadataIndex, request.queryText(), baseDocIds, metadataFilter);
            case "manual" -> applyManualFilter(metadataIndex, metadataFilter, baseDocIds);
            default -> baseDocIds;
        };
    }

    private List<String> applyAutoFilter(
        Map<String, Map<String, Set<String>>> metadataIndex,
        String queryText,
        List<String> baseDocIds,
        Map<String, String> constraints
    ) {
        MetaFilterResult generated = generateMetaFilter(metadataIndex, queryText, constraints);
        if (generated.conditions().isEmpty()) {
            return baseDocIds;
        }
        return applyConditions(metadataIndex, generated.conditions(), generated.logic(), baseDocIds);
    }

    private List<String> applySemiAutoFilter(
        Map<String, Map<String, Set<String>>> metadataIndex,
        String queryText,
        List<String> baseDocIds,
        Map<String, Object> metadataFilter
    ) {
        List<?> semiAuto = metadataFilter.get("semi_auto") instanceof List<?> list ? list : List.of();
        Map<String, Map<String, Set<String>>> filteredMetadata = new LinkedHashMap<>();
        Map<String, String> constraints = new LinkedHashMap<>();
        for (Object item : semiAuto) {
            if (item instanceof String key && metadataIndex.containsKey(key)) {
                filteredMetadata.put(key, metadataIndex.get(key));
            } else if (item instanceof Map<?, ?> map) {
                String key = stringValue(map.get("key"));
                if (metadataIndex.containsKey(key)) {
                    filteredMetadata.put(key, metadataIndex.get(key));
                    String op = stringValue(map.get("op"));
                    if (!op.isBlank()) {
                        constraints.put(key, op);
                    }
                }
            }
        }
        if (filteredMetadata.isEmpty()) {
            return baseDocIds;
        }
        return applyAutoFilter(filteredMetadata, queryText, baseDocIds, constraints);
    }

    private List<String> applyManualFilter(
        Map<String, Map<String, Set<String>>> metadataIndex,
        Map<String, Object> metadataFilter,
        List<String> baseDocIds
    ) {
        List<?> rawConditions = metadataFilter.get("manual") instanceof List<?> list ? list : List.of();
        List<MetaFilterCondition> conditions = new ArrayList<>();
        for (Object item : rawConditions) {
            if (item instanceof Map<?, ?> map) {
                conditions.add(new MetaFilterCondition(
                    stringValue(map.get("key")),
                    stringValue(map.get("value")),
                    stringValue(map.get("op"))
                ));
            }
        }
        if (conditions.isEmpty()) {
            return baseDocIds;
        }
        String logic = stringValue(metadataFilter.get("logic"));
        return applyConditions(metadataIndex, conditions, logic.isBlank() ? "and" : logic, baseDocIds);
    }

    private MetaFilterResult generateMetaFilter(
        Map<String, Map<String, Set<String>>> metadataIndex,
        String queryText,
        Map<String, String> constraints
    ) {
        String prompt = promptTemplateRepository.load("meta_filter.md");
        String rendered = prompt
            .replace("{{ current_date }}", LocalDate.now().toString())
            .replace("{{ metadata_keys }}", toJson(metadataIndex.keySet()))
            .replace("{{ user_question }}", queryText == null ? "" : queryText)
            .replace("{{ constraints }}", constraints.isEmpty() ? "" : "Operator constraints: " + toJson(constraints));
        return promptModelClient.complete(rendered, "Generate filters:", 0.0d)
            .map(this::parseMetaFilterResult)
            .orElse(new MetaFilterResult(List.of(), "and"));
    }

    private MetaFilterResult parseMetaFilterResult(String rawResponse) {
        try {
            String cleaned = rawResponse
                .replace("```json", "")
                .replace("```", "")
                .trim();
            Map<?, ?> parsed = objectMapper.readValue(cleaned, Map.class);
            String logic = stringValue(parsed.get("logic"));
            List<MetaFilterCondition> conditions = new ArrayList<>();
            if (parsed.get("conditions") instanceof List<?> list) {
                for (Object item : list) {
                    if (item instanceof Map<?, ?> map) {
                        conditions.add(new MetaFilterCondition(
                            stringValue(map.get("key")),
                            stringValue(map.get("value")),
                            stringValue(map.get("op"))
                        ));
                    }
                }
            }
            return new MetaFilterResult(conditions, logic.isBlank() ? "and" : logic);
        } catch (Exception ignored) {
            return new MetaFilterResult(List.of(), "and");
        }
    }

    private List<String> applyConditions(
        Map<String, Map<String, Set<String>>> metadataIndex,
        List<MetaFilterCondition> conditions,
        String logic,
        List<String> baseDocIds
    ) {
        Set<String> scopedBaseDocIds = new LinkedHashSet<>(baseDocIds);
        Set<String> result = new LinkedHashSet<>();
        boolean first = true;
        for (MetaFilterCondition condition : conditions) {
            Set<String> matched = applySingleCondition(metadataIndex, condition);
            matched.retainAll(scopedBaseDocIds);
            if (first) {
                result.addAll(matched);
                first = false;
                continue;
            }
            if ("or".equalsIgnoreCase(logic)) {
                result.addAll(matched);
            } else {
                result.retainAll(matched);
            }
        }
        return result.isEmpty() && !conditions.isEmpty() ? List.of("-999") : result.stream().toList();
    }

    private Set<String> applySingleCondition(
        Map<String, Map<String, Set<String>>> metadataIndex,
        MetaFilterCondition condition
    ) {
        Map<String, Set<String>> values = metadataIndex.getOrDefault(condition.key(), Map.of());
        Set<String> result = new LinkedHashSet<>();
        String op = condition.op().isBlank() ? "=" : condition.op().toLowerCase(Locale.ROOT);
        String value = condition.value();
        switch (op) {
            case "=", "==":
                result.addAll(values.getOrDefault(value, Set.of()));
                break;
            case "!=", "≠":
                for (Map.Entry<String, Set<String>> entry : values.entrySet()) {
                    if (!entry.getKey().equals(value)) {
                        result.addAll(entry.getValue());
                    }
                }
                break;
            case "contains":
                for (Map.Entry<String, Set<String>> entry : values.entrySet()) {
                    if (entry.getKey().toLowerCase(Locale.ROOT).contains(value.toLowerCase(Locale.ROOT))) {
                        result.addAll(entry.getValue());
                    }
                }
                break;
            case "not contains":
                for (Map.Entry<String, Set<String>> entry : values.entrySet()) {
                    if (!entry.getKey().toLowerCase(Locale.ROOT).contains(value.toLowerCase(Locale.ROOT))) {
                        result.addAll(entry.getValue());
                    }
                }
                break;
            case "in":
                for (String item : splitCsv(value)) {
                    result.addAll(values.getOrDefault(item, Set.of()));
                }
                break;
            case "not in":
                Set<String> excluded = new LinkedHashSet<>(splitCsv(value));
                for (Map.Entry<String, Set<String>> entry : values.entrySet()) {
                    if (!excluded.contains(entry.getKey())) {
                        result.addAll(entry.getValue());
                    }
                }
                break;
            case "start with":
                for (Map.Entry<String, Set<String>> entry : values.entrySet()) {
                    if (entry.getKey().toLowerCase(Locale.ROOT).startsWith(value.toLowerCase(Locale.ROOT))) {
                        result.addAll(entry.getValue());
                    }
                }
                break;
            case "end with":
                for (Map.Entry<String, Set<String>> entry : values.entrySet()) {
                    if (entry.getKey().toLowerCase(Locale.ROOT).endsWith(value.toLowerCase(Locale.ROOT))) {
                        result.addAll(entry.getValue());
                    }
                }
                break;
            default:
                result.addAll(values.getOrDefault(value, Set.of()));
                break;
        }
        return result;
    }

    private Map<String, Map<String, Set<String>>> buildMetadataIndex(List<CollectionRetrievalPlan> plans) {
        Map<String, Map<String, Set<String>>> metadataIndex = new LinkedHashMap<>();
        for (CollectionRetrievalPlan plan : plans) {
            Set<String> allowed = new LinkedHashSet<>(plan.allowedDocIds());
            Map<String, Map<String, Object>> publishedMetadata = buildPublishedMetadataIndex(plan);
            for (IndexedChunk chunk : knowledgeStore.listChunks(plan.collectionId())) {
                if (!allowed.contains(chunk.finalDocId())) {
                    continue;
                }
                Map<String, Object> flattened = new LinkedHashMap<>();
                flattened.putAll(publishedMetadata.getOrDefault(chunk.finalDocId(), Map.of()));
                flattened.putAll(flattenChunkMetadata(chunk.metadata()));
                for (Map.Entry<String, Object> entry : flattened.entrySet()) {
                    if (entry.getValue() == null) {
                        continue;
                    }
                    metadataIndex
                        .computeIfAbsent(entry.getKey(), ignored -> new LinkedHashMap<>())
                        .computeIfAbsent(String.valueOf(entry.getValue()), ignored -> new LinkedHashSet<>())
                        .add(chunk.finalDocId());
                }
            }
        }
        return metadataIndex;
    }

    private Map<String, Map<String, Object>> buildPublishedMetadataIndex(CollectionRetrievalPlan plan) {
        Map<String, Map<String, Object>> index = new LinkedHashMap<>();
        List<PublishedDocumentRecord> records = publishedDocumentSource.listByCollection(plan.collectionId());
        for (PublishedDocumentRecord record : records) {
            Map<String, Object> values = new LinkedHashMap<>();
            values.put("published_document_state", record.publishedDocumentState());
            values.put("visibility", record.visibility());
            index.put(record.finalDocId(), values);
        }
        return index;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> flattenChunkMetadata(Map<String, Object> metadata) {
        Map<String, Object> flattened = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : metadata.entrySet()) {
            if (entry.getValue() instanceof Map<?, ?> || entry.getValue() instanceof List<?>) {
                continue;
            }
            flattened.put(entry.getKey(), entry.getValue());
        }
        if (metadata.get("doc_metadata") instanceof Map<?, ?> docMetadata) {
            for (Map.Entry<?, ?> entry : docMetadata.entrySet()) {
                if (!(entry.getValue() instanceof Map<?, ?>) && !(entry.getValue() instanceof List<?>)) {
                    flattened.put(String.valueOf(entry.getKey()), entry.getValue());
                }
            }
        }
        return flattened;
    }

    private List<String> splitCsv(String value) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        return List.of(value.split(",")).stream().map(String::trim).filter(item -> !item.isBlank()).toList();
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException error) {
            return "[]";
        }
    }

    public record MetaFilterCondition(String key, String value, String op) {}

    public record MetaFilterResult(List<MetaFilterCondition> conditions, String logic) {}
}

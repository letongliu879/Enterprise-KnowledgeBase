package com.realityrag.retrieval.preprocess;

import com.realityrag.retrieval.config.RetrievalSearchStrategyProperties;
import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.prompt.PromptModelClient;
import com.realityrag.retrieval.prompt.PromptTemplateRepository;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Component;

@Component
public class QueryPreparationService {
    private final RetrievalSearchStrategyProperties strategyProperties;
    private final PromptModelClient promptModelClient;
    private final PromptTemplateRepository promptTemplateRepository;
    private final MetadataFilterService metadataFilterService;

    public QueryPreparationService(
        RetrievalSearchStrategyProperties strategyProperties,
        PromptModelClient promptModelClient,
        PromptTemplateRepository promptTemplateRepository,
        MetadataFilterService metadataFilterService
    ) {
        this.strategyProperties = strategyProperties;
        this.promptModelClient = promptModelClient;
        this.promptTemplateRepository = promptTemplateRepository;
        this.metadataFilterService = metadataFilterService;
    }

    public PreparedQuery prepare(RetrieveRequest request, List<CollectionRetrievalPlan> plans) {
        List<String> allowedDocIds = metadataFilterService.resolveAllowedDocIds(request, plans);
        String queryText = request.queryText();

        if (strategyProperties.isEnableRagflowCrossLanguages() && !request.crossLanguages().isEmpty()) {
            queryText = translateCrossLanguages(queryText, request.crossLanguages()).orElse(queryText);
        }

        if (strategyProperties.isEnableRagflowKeywordExtraction() && Boolean.TRUE.equals(request.keyword())) {
            Optional<String> keywords = extractKeywords(queryText);
            if (keywords.isPresent() && !keywords.get().isBlank()) {
                queryText = queryText + " " + keywords.get();
            }
        }

        return new PreparedQuery(queryText, allowedDocIds);
    }

    private Optional<String> extractKeywords(String queryText) {
        String systemPrompt = renderKeywordPrompt(queryText, strategyProperties.getRagflowKeywordTopN());
        return promptModelClient.complete(systemPrompt, "Output: ", 0.2d)
            .map(this::stripThinkingAndCodeFences);
    }

    private Optional<String> translateCrossLanguages(String queryText, List<String> languages) {
        String systemPrompt = promptTemplateRepository.load("cross_languages_sys_prompt.md");
        String userPrompt = promptTemplateRepository.load("cross_languages_user_prompt.md")
            .replace("{{ query }}", queryText)
            .replace("{{ languages }}", String.join(", ", languages));
        return promptModelClient.complete(systemPrompt, userPrompt, 0.2d)
            .map(this::stripThinkingAndCodeFences)
            .map(raw -> raw.replace("Output:", "").replace("output:", "").trim())
            .filter(raw -> !raw.isBlank());
    }

    private String renderKeywordPrompt(String content, int topN) {
        return promptTemplateRepository.load("keyword_prompt.md")
            .replace("{{ content }}", content)
            .replace("{{ topn }}", String.valueOf(topN));
    }

    private String stripThinkingAndCodeFences(String raw) {
        return raw
            .replaceAll("(?s)^.*?</think>", "")
            .replace("```json", "")
            .replace("```", "")
            .trim();
    }

    public record PreparedQuery(String queryText, List<String> allowedDocIds) {}
}

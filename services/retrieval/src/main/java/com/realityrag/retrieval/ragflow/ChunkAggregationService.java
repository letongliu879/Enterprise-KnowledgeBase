package com.realityrag.retrieval.ragflow;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.config.RetrievalSearchStrategyProperties;
import com.realityrag.retrieval.prompt.PromptModelClient;
import com.realityrag.retrieval.prompt.PromptTemplateRepository;
import com.realityrag.retrieval.recall.RetrievedChunk;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.store.KnowledgeStore;
import com.realityrag.retrieval.toc.DocumentTocNode;
import com.realityrag.retrieval.toc.DocumentTocSource;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

@Component
public class ChunkAggregationService {
    private final DocumentTocSource documentTocSource;
    private final KnowledgeStore knowledgeStore;
    private final RetrievalSearchStrategyProperties strategyProperties;
    private final PromptModelClient promptModelClient;
    private final PromptTemplateRepository promptTemplateRepository;
    private final ObjectMapper objectMapper;

    public ChunkAggregationService(
        DocumentTocSource documentTocSource,
        KnowledgeStore knowledgeStore,
        RetrievalSearchStrategyProperties strategyProperties,
        PromptModelClient promptModelClient,
        PromptTemplateRepository promptTemplateRepository,
        ObjectMapper objectMapper
    ) {
        this.documentTocSource = documentTocSource;
        this.knowledgeStore = knowledgeStore;
        this.strategyProperties = strategyProperties;
        this.promptModelClient = promptModelClient;
        this.promptTemplateRepository = promptTemplateRepository;
        this.objectMapper = objectMapper;
    }

    // ---- TOC Aggregation ----

    public List<RetrievedChunk> aggregateByToc(String queryText, List<RetrievedChunk> chunks) {
        if (!strategyProperties.isEnableRagflowTocAggregation() || chunks.isEmpty()) {
            return chunks;
        }

        RetrievedChunk anchorChunk = selectAnchorDocument(chunks);
        if (anchorChunk == null) {
            return chunks;
        }

        List<DocumentTocNode> tocNodes = documentTocSource.listByDocument(
            anchorChunk.chunk().collectionId(),
            anchorChunk.chunk().finalDocId()
        );
        if (tocNodes.isEmpty()) {
            return chunks;
        }

        List<ScoredTocNode> selectedNodes = selectRelevantTocNodes(queryText, tocNodes);
        if (selectedNodes.isEmpty()) {
            return chunks;
        }

        Map<String, RetrievedChunk> deduped = chunks.stream()
            .collect(Collectors.toMap(
                item -> item.chunk().chunkId(),
                item -> item,
                (left, right) -> left,
                LinkedHashMap::new
            ));

        for (ScoredTocNode selectedNode : selectedNodes) {
            for (String chunkId : selectedNode.node().linkedChunkIds()) {
                RetrievedChunk existing = deduped.get(chunkId);
                if (existing != null) {
                    deduped.put(chunkId, new RetrievedChunk(
                        existing.chunk(),
                        Math.max(existing.score(), clampScore(existing.score() + selectedNode.score())),
                        "ragflow_toc_aggregate",
                        "Boosted by TOC node '" + selectedNode.node().title() + "'."
                    ));
                    continue;
                }

                IndexedChunk indexedChunk = lookupChunk(anchorChunk, chunkId);
                if (indexedChunk == null) {
                    continue;
                }
                deduped.put(chunkId, new RetrievedChunk(
                    indexedChunk,
                    selectedNode.score(),
                    "ragflow_toc_aggregate",
                    "Added from TOC node '" + selectedNode.node().title() + "'."
                ));
            }
        }

        return deduped.values().stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .limit(strategyProperties.getRagflowTocTopN())
            .toList();
    }

    // ---- Children Aggregation ----

    public List<RetrievedChunk> aggregateByChildren(List<RetrievedChunk> chunks) {
        if (!strategyProperties.isEnableRagflowChildrenAggregation() || chunks.isEmpty()) {
            return chunks;
        }

        List<RetrievedChunk> remaining = new ArrayList<>();
        Map<String, List<RetrievedChunk>> byParentChunk = new LinkedHashMap<>();
        for (RetrievedChunk chunk : chunks) {
            String parentChunkId = parentChunkId(chunk);
            if (parentChunkId == null) {
                remaining.add(chunk);
                continue;
            }
            byParentChunk.computeIfAbsent(parentChunkId, ignored -> new ArrayList<>()).add(chunk);
        }

        if (byParentChunk.isEmpty()) {
            return chunks;
        }

        Map<String, RetrievedChunk> deduped = new LinkedHashMap<>();
        for (RetrievedChunk chunk : remaining) {
            deduped.put(chunk.chunk().chunkId(), chunk);
        }
        for (Map.Entry<String, List<RetrievedChunk>> entry : byParentChunk.entrySet()) {
            List<RetrievedChunk> childChunks = entry.getValue();
            IndexedChunk parent = lookupParentChunk(entry.getKey(), childChunks.get(0));
            if (parent == null) {
                for (RetrievedChunk childChunk : childChunks) {
                    deduped.putIfAbsent(childChunk.chunk().chunkId(), childChunk);
                }
                continue;
            }

            double meanScore = childChunks.stream()
                .mapToDouble(RetrievedChunk::score)
                .average()
                .orElse(0.0d);
            RetrievedChunk aggregatedParent = new RetrievedChunk(
                parent,
                meanScore,
                "ragflow_children_aggregate",
                "Aggregated child chunks into parent chunk using mom_id."
            );
            RetrievedChunk existing = deduped.get(parent.chunkId());
            if (existing == null || aggregatedParent.score() >= existing.score()) {
                deduped.put(parent.chunkId(), aggregatedParent);
            }
        }

        return deduped.values().stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .toList();
    }

    // ---- TOC helpers ----

    private RetrievedChunk selectAnchorDocument(List<RetrievedChunk> chunks) {
        return chunks.stream()
            .collect(Collectors.groupingBy(
                item -> item.chunk().collectionId() + "::" + item.chunk().finalDocId(),
                LinkedHashMap::new,
                Collectors.summingDouble(RetrievedChunk::score)
            ))
            .entrySet().stream()
            .max(Map.Entry.comparingByValue())
            .flatMap(entry -> chunks.stream().filter(item ->
                (item.chunk().collectionId() + "::" + item.chunk().finalDocId()).equals(entry.getKey())
            ).findFirst())
            .orElse(null);
    }

    private List<ScoredTocNode> selectRelevantTocNodes(String queryText, List<DocumentTocNode> tocNodes) {
        Set<String> queryTokens = tokenize(queryText);
        if (queryTokens.isEmpty()) {
            return List.of();
        }

        if (strategyProperties.isEnableRagflowTocLlmSelector()) {
            List<ScoredTocNode> llmSelected = selectRelevantTocNodesByLlm(queryText, tocNodes);
            if (!llmSelected.isEmpty()) {
                return llmSelected;
            }
        }

        return tocNodes.stream()
            .map(node -> new ScoredTocNode(node, scoreTocNode(queryTokens, node)))
            .filter(item -> item.score() >= strategyProperties.getRagflowTocMinScore())
            .sorted(Comparator.comparingDouble(ScoredTocNode::score).reversed())
            .limit(strategyProperties.getRagflowTocTopN() * 2L)
            .toList();
    }

    private List<ScoredTocNode> selectRelevantTocNodesByLlm(String queryText, List<DocumentTocNode> tocNodes) {
        try {
            String systemPrompt = promptTemplateRepository.load("toc_relevance_system.md");
            String tocJson = objectMapper.writeValueAsString(
                tocNodes.stream()
                    .map(node -> Map.of("level", node.level(), "title", node.title()))
                    .toList()
            );
            String userPrompt = promptTemplateRepository.load("toc_relevance_user.md")
                .replace("{{ query }}", queryText == null ? "" : queryText)
                .replace("{{ toc_json }}", tocJson);
            return promptModelClient.complete(systemPrompt, userPrompt, 0.0d)
                .map(this::parseTocScores)
                .map(scores -> mergeTocScores(tocNodes, scores))
                .orElse(List.of());
        } catch (Exception ignored) {
            return List.of();
        }
    }

    private List<Double> parseTocScores(String rawResponse) {
        try {
            String cleaned = rawResponse
                .replaceAll("(?s)^.*?</think>", "")
                .replace("```json", "")
                .replace("```", "")
                .trim();
            List<?> parsed = objectMapper.readValue(cleaned, List.class);
            List<Double> scores = new ArrayList<>();
            for (Object item : parsed) {
                if (item instanceof Map<?, ?> map) {
                    Object value = map.get("score");
                    if (value instanceof Number number) {
                        scores.add(number.doubleValue() / 5.0d);
                    } else {
                        scores.add(0.0d);
                    }
                } else {
                    scores.add(0.0d);
                }
            }
            return scores;
        } catch (Exception ignored) {
            return List.of();
        }
    }

    private List<ScoredTocNode> mergeTocScores(List<DocumentTocNode> tocNodes, List<Double> scores) {
        List<ScoredTocNode> selected = new ArrayList<>();
        int size = Math.min(tocNodes.size(), scores.size());
        for (int index = 0; index < size; index++) {
            double score = scores.get(index);
            if (score >= strategyProperties.getRagflowTocMinScore()) {
                selected.add(new ScoredTocNode(tocNodes.get(index), score));
            }
        }
        return selected.stream()
            .sorted(Comparator.comparingDouble(ScoredTocNode::score).reversed())
            .limit(strategyProperties.getRagflowTocTopN() * 2L)
            .toList();
    }

    private double scoreTocNode(Set<String> queryTokens, DocumentTocNode node) {
        Set<String> titleTokens = new LinkedHashSet<>();
        titleTokens.addAll(tokenize(node.title()));
        for (String pathSegment : node.tocPath()) {
            titleTokens.addAll(tokenize(pathSegment));
        }
        if (titleTokens.isEmpty()) {
            return 0.0d;
        }
        long matched = queryTokens.stream().filter(titleTokens::contains).count();
        return matched == 0 ? 0.0d : (double) matched / queryTokens.size();
    }

    private IndexedChunk lookupChunk(RetrievedChunk anchorChunk, String chunkId) {
        return knowledgeStore.listChunks(anchorChunk.chunk().collectionId()).stream()
            .filter(chunk -> anchorChunk.chunk().finalDocId().equals(chunk.finalDocId()))
            .filter(chunk -> chunk.chunkId().equals(chunkId))
            .findFirst()
            .orElse(null);
    }

    // ---- Children helpers ----

    private IndexedChunk lookupParentChunk(String parentChunkId, RetrievedChunk childChunk) {
        return knowledgeStore.listChunks(childChunk.chunk().collectionId()).stream()
            .filter(chunk -> parentChunkId.equals(chunk.chunkId()))
            .findFirst()
            .orElse(null);
    }

    private String parentChunkId(RetrievedChunk chunk) {
        Object value = chunk.chunk().metadata().get("mom_id");
        if (value == null) {
            return null;
        }
        String parentChunkId = String.valueOf(value).trim();
        return parentChunkId.isBlank() ? null : parentChunkId;
    }

    // ---- Shared helpers ----

    private Set<String> tokenize(String rawText) {
        if (rawText == null || rawText.isBlank()) {
            return Set.of();
        }
        Set<String> tokens = new LinkedHashSet<>();
        for (String token : rawText.toLowerCase(Locale.ROOT).replaceAll("[^\\p{IsAlphabetic}\\p{IsDigit}\\s]+", " ").split("\\s+")) {
            if (!token.isBlank()) {
                tokens.add(token);
            }
        }
        return tokens;
    }

    private double clampScore(double value) {
        return Math.max(0.0d, Math.min(1.0d, value));
    }

    private record ScoredTocNode(DocumentTocNode node, double score) {}
}

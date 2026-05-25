package com.realityrag.retrieval.expansion;

import com.realityrag.retrieval.config.RetrievalSearchStrategyProperties;
import com.realityrag.retrieval.recall.RetrievedChunk;
import com.realityrag.retrieval.store.IndexedChunk;
import com.realityrag.retrieval.store.KnowledgeStore;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class BreadcrumbChunkExpander {
    private final KnowledgeStore knowledgeStore;
    private final RetrievalSearchStrategyProperties strategyProperties;

    public BreadcrumbChunkExpander(
        KnowledgeStore knowledgeStore,
        RetrievalSearchStrategyProperties strategyProperties
    ) {
        this.knowledgeStore = knowledgeStore;
        this.strategyProperties = strategyProperties;
    }

    public List<RetrievedChunk> expand(List<RetrievedChunk> seeds) {
        if (seeds.isEmpty() || !strategyProperties.isEnableBreadcrumbExpansion()) {
            return List.of();
        }

        Map<String, RetrievedChunk> existing = new LinkedHashMap<>();
        for (RetrievedChunk seed : seeds) {
            existing.put(seed.chunk().chunkId(), seed);
        }

        List<RetrievedChunk> expanded = new ArrayList<>();
        Map<String, List<RetrievedChunk>> byPrefix = groupByPrefix(seeds);
        for (Map.Entry<String, List<RetrievedChunk>> entry : byPrefix.entrySet()) {
            String prefix = entry.getKey();
            List<RetrievedChunk> prefixSeeds = entry.getValue();
            if (prefix.isBlank()) {
                continue;
            }

            IndexedChunk reference = prefixSeeds.get(0).chunk();
            List<IndexedChunk> chunks = knowledgeStore.listChunks(reference.collectionId()).stream()
                .filter(chunk -> chunk.finalDocId().equals(reference.finalDocId()))
                .filter(chunk -> prefix.equals(extractSectionPrefix(chunk.sectionPath())))
                .filter(chunk -> !existing.containsKey(chunk.chunkId()))
                .sorted(Comparator.comparingInt(this::extractChunkOrder))
                .limit(strategyProperties.getBreadcrumbExpandLimit())
                .toList();

            double maxSeedScore = prefixSeeds.stream()
                .mapToDouble(RetrievedChunk::score)
                .max()
                .orElse(0.0d);

            for (IndexedChunk chunk : chunks) {
                RetrievedChunk expandedChunk = new RetrievedChunk(
                    chunk,
                    maxSeedScore * strategyProperties.getDecayBreadcrumb(),
                    "breadcrumb_expand",
                    "Expanded from same section-path prefix as seed result."
                );
                existing.put(chunk.chunkId(), expandedChunk);
                expanded.add(expandedChunk);
            }
        }

        return expanded.stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .toList();
    }

    private Map<String, List<RetrievedChunk>> groupByPrefix(List<RetrievedChunk> seeds) {
        Map<String, List<RetrievedChunk>> grouped = new LinkedHashMap<>();
        for (RetrievedChunk seed : seeds) {
            String prefix = extractSectionPrefix(seed.chunk().sectionPath());
            if (prefix == null) {
                continue;
            }
            grouped.computeIfAbsent(prefix, ignored -> new ArrayList<>()).add(seed);
        }
        return grouped;
    }

    private String extractSectionPrefix(List<String> sectionPath) {
        if (sectionPath == null || sectionPath.size() <= 1) {
            return null;
        }
        return String.join(" > ", sectionPath.subList(0, sectionPath.size() - 1));
    }

    private int extractChunkOrder(IndexedChunk chunk) {
        int idx = chunk.chunkId().lastIndexOf('_');
        if (idx < 0 || idx + 1 >= chunk.chunkId().length()) {
            return Integer.MAX_VALUE;
        }
        try {
            return Integer.parseInt(chunk.chunkId().substring(idx + 1));
        } catch (NumberFormatException ignored) {
            return Integer.MAX_VALUE;
        }
    }
}

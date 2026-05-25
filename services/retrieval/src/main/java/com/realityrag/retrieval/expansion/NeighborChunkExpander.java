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
public class NeighborChunkExpander {
    private final KnowledgeStore knowledgeStore;
    private final RetrievalSearchStrategyProperties strategyProperties;

    public NeighborChunkExpander(
        KnowledgeStore knowledgeStore,
        RetrievalSearchStrategyProperties strategyProperties
    ) {
        this.knowledgeStore = knowledgeStore;
        this.strategyProperties = strategyProperties;
    }

    public List<RetrievedChunk> expand(List<RetrievedChunk> seeds) {
        if (seeds.isEmpty() || !strategyProperties.isEnableNeighborExpansion()) {
            return List.of();
        }

        Map<String, RetrievedChunk> existing = new LinkedHashMap<>();
        for (RetrievedChunk seed : seeds) {
            existing.put(seed.chunk().chunkId(), seed);
        }

        List<RetrievedChunk> expanded = new ArrayList<>();
        Map<String, List<RetrievedChunk>> grouped = groupByDocument(seeds);
        for (Map.Entry<String, List<RetrievedChunk>> entry : grouped.entrySet()) {
            List<RetrievedChunk> perDocSeeds = entry.getValue();
            IndexedChunk reference = perDocSeeds.get(0).chunk();
            List<IndexedChunk> chunks = knowledgeStore.listChunks(reference.collectionId()).stream()
                .filter(chunk -> chunk.finalDocId().equals(reference.finalDocId()))
                .sorted(Comparator.comparingInt(this::extractChunkOrder))
                .toList();

            Map<Integer, IndexedChunk> byOrder = new LinkedHashMap<>();
            for (IndexedChunk chunk : chunks) {
                byOrder.put(extractChunkOrder(chunk), chunk);
            }

            for (RetrievedChunk seed : perDocSeeds) {
                int seedOrder = extractChunkOrder(seed.chunk());
                for (int delta = -strategyProperties.getNeighborHops(); delta <= strategyProperties.getNeighborHops(); delta++) {
                    if (delta == 0) {
                        continue;
                    }
                    int neighborOrder = seedOrder + delta;
                    IndexedChunk neighbor = byOrder.get(neighborOrder);
                    if (neighbor == null || existing.containsKey(neighbor.chunkId())) {
                        continue;
                    }
                    double score = seed.score() * Math.pow(strategyProperties.getDecayNeighbor(), Math.abs(delta));
                    RetrievedChunk expandedChunk = new RetrievedChunk(
                        neighbor,
                        score,
                        "neighbor_expand",
                        "Expanded from adjacent chunk around seed result."
                    );
                    existing.put(neighbor.chunkId(), expandedChunk);
                    expanded.add(expandedChunk);
                }
            }
        }

        return expanded.stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .toList();
    }

    private Map<String, List<RetrievedChunk>> groupByDocument(List<RetrievedChunk> seeds) {
        return seeds.stream()
            .collect(java.util.stream.Collectors.groupingBy(
                seed -> seed.chunk().collectionId() + "::" + seed.chunk().finalDocId(),
                LinkedHashMap::new,
                java.util.stream.Collectors.toList()
            ));
    }

    private int extractChunkOrder(IndexedChunk chunk) {
        return extractChunkOrder(chunk.chunkId());
    }

    private int extractChunkOrder(String chunkId) {
        int idx = chunkId.lastIndexOf('_');
        if (idx < 0 || idx + 1 >= chunkId.length()) {
            return Integer.MAX_VALUE;
        }
        try {
            return Integer.parseInt(chunkId.substring(idx + 1));
        } catch (NumberFormatException ignored) {
            return Integer.MAX_VALUE;
        }
    }
}

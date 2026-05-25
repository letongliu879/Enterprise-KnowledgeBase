package com.realityrag.retrieval.cutoff;

import com.realityrag.retrieval.config.RetrievalSearchStrategyProperties;
import com.realityrag.retrieval.recall.RetrievedChunk;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class SmartTopKCutoffService {
    private final RetrievalSearchStrategyProperties strategyProperties;

    public SmartTopKCutoffService(RetrievalSearchStrategyProperties strategyProperties) {
        this.strategyProperties = strategyProperties;
    }

    public List<RetrievedChunk> selectSeeds(List<RetrievedChunk> fusedChunks) {
        if (fusedChunks.isEmpty()) {
            return List.of();
        }

        List<RetrievedChunk> sorted = fusedChunks.stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::score).reversed())
            .limit(strategyProperties.getFusedTopM())
            .toList();

        if (!strategyProperties.isEnableSmartTopK()) {
            return deduplicate(sorted);
        }

        double topScore = sorted.get(0).score();
        if (topScore < strategyProperties.getSmartMinScore()) {
            return List.of(sorted.get(0));
        }

        double ratioThreshold = topScore * strategyProperties.getSmartTopScoreRatio();
        double deltaThreshold = topScore - strategyProperties.getSmartTopScoreDeltaAbs();
        double dynamicThreshold = Math.max(
            strategyProperties.getSmartMinScore(),
            Math.min(ratioThreshold, deltaThreshold)
        );

        List<RetrievedChunk> selected = new ArrayList<>();
        for (int index = 0; index < sorted.size(); index++) {
            RetrievedChunk chunk = sorted.get(index);
            if (selected.size() >= strategyProperties.getSmartMaxK()) {
                break;
            }
            if (index < strategyProperties.getSmartMinK()) {
                if (chunk.score() >= strategyProperties.getSmartMinScore()) {
                    selected.add(chunk);
                    continue;
                }
                break;
            }
            if (chunk.score() < dynamicThreshold) {
                break;
            }
            selected.add(chunk);
        }

        List<RetrievedChunk> deduped = deduplicate(selected);
        int minRequired = Math.min(strategyProperties.getSmartMinK(), strategyProperties.getSmartMaxK());
        if (deduped.size() < minRequired) {
            java.util.Set<String> seen = deduped.stream()
                .map(item -> item.chunk().chunkId())
                .collect(java.util.stream.Collectors.toCollection(java.util.LinkedHashSet::new));
            for (RetrievedChunk chunk : sorted) {
                if (deduped.size() >= minRequired) {
                    break;
                }
                if (chunk.score() < strategyProperties.getSmartMinScore()) {
                    break;
                }
                if (seen.add(chunk.chunk().chunkId())) {
                    deduped.add(chunk);
                }
            }
        }
        return deduped;
    }

    private List<RetrievedChunk> deduplicate(List<RetrievedChunk> chunks) {
        Map<String, RetrievedChunk> deduped = new LinkedHashMap<>();
        for (RetrievedChunk chunk : chunks) {
            deduped.putIfAbsent(chunk.chunk().chunkId(), chunk);
        }
        return new ArrayList<>(deduped.values());
    }
}

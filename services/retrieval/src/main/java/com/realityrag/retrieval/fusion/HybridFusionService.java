package com.realityrag.retrieval.fusion;

import com.realityrag.retrieval.recall.BackendRecallHit;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class HybridFusionService {
    public List<BackendRecallHit> fuse(List<BackendRecallHit> hits) {
        Map<String, BackendRecallHit> fused = new LinkedHashMap<>();
        for (BackendRecallHit hit : hits) {
            String key = hit.chunk().chunkId();
            fused.merge(
                key,
                hit,
                (left, right) -> new BackendRecallHit(
                    left.chunk(),
                    Math.max(left.score(), right.score()),
                    left.backendName() + "+" + right.backendName(),
                    mergeExplanation(left, right)
                )
            );
        }
        return fused.values().stream()
            .sorted(Comparator.comparingDouble(BackendRecallHit::score).reversed())
            .toList();
    }

    private String mergeExplanation(BackendRecallHit left, BackendRecallHit right) {
        if (left.whySelected().equals(right.whySelected())) {
            return left.whySelected();
        }
        return left.whySelected() + " " + right.whySelected();
    }
}

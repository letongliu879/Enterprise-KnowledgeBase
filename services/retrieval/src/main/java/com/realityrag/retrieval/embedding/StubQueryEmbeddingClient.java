package com.realityrag.retrieval.embedding;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public class StubQueryEmbeddingClient implements QueryEmbeddingClient {
    @Override
    public List<Double> embed(String queryText, String embeddingModel) {
        byte[] bytes = (embeddingModel + ":" + queryText).getBytes(StandardCharsets.UTF_8);
        List<Double> vector = new ArrayList<>();
        for (int index = 0; index < Math.min(bytes.length, 16); index++) {
            vector.add((bytes[index] & 0xFF) / 255.0d);
        }
        while (vector.size() < 16) {
            vector.add(0.0d);
        }
        return vector;
    }
}

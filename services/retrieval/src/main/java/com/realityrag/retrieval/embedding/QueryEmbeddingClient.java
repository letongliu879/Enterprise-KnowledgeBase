package com.realityrag.retrieval.embedding;

import java.util.List;

public interface QueryEmbeddingClient {
    List<Double> embed(String queryText, String embeddingModel);
}

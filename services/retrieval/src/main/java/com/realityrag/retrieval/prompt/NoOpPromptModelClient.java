package com.realityrag.retrieval.prompt;

import java.util.Optional;
public class NoOpPromptModelClient implements PromptModelClient {
    @Override
    public Optional<String> complete(String systemPrompt, String userPrompt, double temperature) {
        return Optional.empty();
    }
}

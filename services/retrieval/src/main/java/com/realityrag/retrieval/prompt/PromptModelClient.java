package com.realityrag.retrieval.prompt;

import java.util.List;
import java.util.Optional;

public interface PromptModelClient {
    Optional<String> complete(String systemPrompt, String userPrompt, double temperature);

    record Message(String role, String content) {}

    default Optional<String> complete(List<Message> messages, double temperature) {
        if (messages == null || messages.isEmpty()) {
            return Optional.empty();
        }
        String systemPrompt = "";
        String userPrompt = "";
        for (Message message : messages) {
            if ("system".equalsIgnoreCase(message.role())) {
                systemPrompt = message.content();
            } else if ("user".equalsIgnoreCase(message.role())) {
                userPrompt = message.content();
            }
        }
        return complete(systemPrompt, userPrompt, temperature);
    }
}

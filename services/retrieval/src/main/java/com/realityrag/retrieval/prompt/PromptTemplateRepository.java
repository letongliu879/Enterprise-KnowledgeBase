package com.realityrag.retrieval.prompt;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

@Component
public class PromptTemplateRepository {
    private final Map<String, String> cache = new ConcurrentHashMap<>();

    public String load(String name) {
        return cache.computeIfAbsent(name, this::readPrompt);
    }

    private String readPrompt(String name) {
        try {
            ClassPathResource resource = new ClassPathResource("prompts/" + name);
            byte[] bytes = resource.getInputStream().readAllBytes();
            return new String(bytes, StandardCharsets.UTF_8);
        } catch (IOException error) {
            throw new IllegalStateException("Failed to load prompt template: " + name, error);
        }
    }
}

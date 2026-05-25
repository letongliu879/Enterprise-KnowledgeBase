package com.realityrag.retrieval.support;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class JsonProjectionReader {
    private JsonProjectionReader() {}

    public static List<Map<String, Object>> readJsonLines(Path path, ObjectMapper objectMapper) {
        if (path == null || !Files.exists(path)) {
            return List.of();
        }
        try {
            List<Map<String, Object>> rows = new ArrayList<>();
            for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
                String trimmed = line.trim();
                if (trimmed.isEmpty()) {
                    continue;
                }
                rows.add(objectMapper.readValue(trimmed, new TypeReference<Map<String, Object>>() {}));
            }
            return rows;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to read projection file: " + path, error);
        }
    }
}

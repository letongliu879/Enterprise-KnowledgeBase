package com.realityrag.retrieval.support;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.contracts.KnowledgeContext;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
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

    public static String stringValue(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        return value == null ? "" : String.valueOf(value);
    }

    public static String coalesce(Map<String, Object> payload, String primary, String fallback) {
        String primaryValue = stringValue(payload, primary);
        return primaryValue.isBlank() ? stringValue(payload, fallback) : primaryValue;
    }

    public static int intValue(Object value, int defaultValue) {
        return value instanceof Number number ? number.intValue() : defaultValue;
    }

    public static double doubleValue(Object value, double defaultValue) {
        return value instanceof Number number ? number.doubleValue() : defaultValue;
    }

    public static boolean booleanValue(Object value) {
        if (value instanceof Boolean bool) {
            return bool;
        }
        return value != null && Boolean.parseBoolean(String.valueOf(value));
    }

    @SuppressWarnings("unchecked")
    public static List<String> stringList(Object raw) {
        if (raw == null) {
            return List.of();
        }
        return ((List<Object>) raw).stream().map(String::valueOf).toList();
    }

    @SuppressWarnings("unchecked")
    public static List<KnowledgeContext.PageSpan> pageSpans(Object raw) {
        if (raw == null) {
            return List.of();
        }
        return ((List<Map<String, Object>>) raw).stream()
            .map(item -> new KnowledgeContext.PageSpan(
                intValue(item.get("page_from"), 1),
                intValue(item.get("page_to"), 1)
            ))
            .toList();
    }

    public static Instant parseInstant(Object value) {
        if (value == null || String.valueOf(value).isBlank()) {
            return Instant.EPOCH;
        }
        return Instant.parse(String.valueOf(value));
    }
}

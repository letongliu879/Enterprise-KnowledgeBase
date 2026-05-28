package com.realityrag.retrieval.profiles;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.contracts.RetrievalProfile;
import com.realityrag.retrieval.support.JsonProjectionReader;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;

public class FileProjectionRetrievalProfileStore implements RetrievalProfileStore {
    private final Path profilesPath;
    private final ObjectMapper objectMapper;

    public FileProjectionRetrievalProfileStore(Path profilesPath, ObjectMapper objectMapper) {
        this.profilesPath = profilesPath;
        this.objectMapper = objectMapper;
    }

    @Override
    public Optional<RetrievalProfile> findByProfileId(String profileId) {
        return JsonProjectionReader.readJsonLines(profilesPath, objectMapper).stream()
            .filter(item -> profileId.equals(stringValue(item, "profile_id")))
            .findFirst()
            .map(this::toProfile);
    }

    @Override
    public Optional<RetrievalProfile> findByProfileId(String profileId, String collectionId) {
        return JsonProjectionReader.readJsonLines(profilesPath, objectMapper).stream()
            .filter(item -> profileId.equals(stringValue(item, "profile_id")))
            .filter(item -> collectionId.equals(stringValue(item, "collection_id")))
            .findFirst()
            .map(this::toProfile)
            .or(() -> findByProfileId(profileId));
    }

    @SuppressWarnings("unchecked")
    private RetrievalProfile toProfile(Map<String, Object> item) {
        return new RetrievalProfile(
            stringValue(item, "profile_id"),
            stringValue(item, "collection_id"),
            intValue(item.get("profile_version"), 1),
            stringValue(item, "profile_hash"),
            doubleValue(item.get("bm25_weight"), 0.5d),
            doubleValue(item.get("vector_weight"), 0.5d),
            intValue(item.get("candidate_top_k"), 20),
            doubleValue(item.get("similarity_threshold"), 0.0d),
            booleanValue(item.get("rerank_enabled")),
            stringValue(item, "rerank_model"),
            stringValue(item, "fail_policy"),
            item.get("expansion_policy") instanceof Map<?, ?> expansion ? (Map<String, Object>) expansion : Map.of(),
            intValue(item.get("pack_budget"), 1200),
            parseInstant(item.get("updated_at")),
            stringValue(item, "updated_by")
        );
    }

    private String stringValue(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        return value == null ? "" : String.valueOf(value);
    }

    private int intValue(Object value, int defaultValue) {
        return value instanceof Number number ? number.intValue() : defaultValue;
    }

    private double doubleValue(Object value, double defaultValue) {
        return value instanceof Number number ? number.doubleValue() : defaultValue;
    }

    private boolean booleanValue(Object value) {
        if (value instanceof Boolean bool) {
            return bool;
        }
        return value != null && Boolean.parseBoolean(String.valueOf(value));
    }

    private Instant parseInstant(Object value) {
        if (value == null || String.valueOf(value).isBlank()) {
            return Instant.EPOCH;
        }
        return Instant.parse(String.valueOf(value));
    }

    @Override
    public void upsert(RetrievalProfile profile) {
        throw new UnsupportedOperationException("FileProjectionRetrievalProfileStore does not support upsert");
    }
}

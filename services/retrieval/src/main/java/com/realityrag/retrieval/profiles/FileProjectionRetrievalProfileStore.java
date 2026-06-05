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
            .filter(item -> profileId.equals(JsonProjectionReader.stringValue(item, "profile_id")))
            .findFirst()
            .map(this::toProfile);
    }

    @Override
    public Optional<RetrievalProfile> findByProfileId(String profileId, String collectionId) {
        return JsonProjectionReader.readJsonLines(profilesPath, objectMapper).stream()
            .filter(item -> profileId.equals(JsonProjectionReader.stringValue(item, "profile_id")))
            .filter(item -> collectionId.equals(JsonProjectionReader.stringValue(item, "collection_id")))
            .findFirst()
            .map(this::toProfile)
            .or(() -> findByProfileId(profileId));
    }

    @SuppressWarnings("unchecked")
    private RetrievalProfile toProfile(Map<String, Object> item) {
        return new RetrievalProfile(
            JsonProjectionReader.stringValue(item, "profile_id"),
            JsonProjectionReader.stringValue(item, "collection_id"),
            JsonProjectionReader.intValue(item.get("profile_version"), 1),
            JsonProjectionReader.stringValue(item, "profile_hash"),
            JsonProjectionReader.doubleValue(item.get("bm25_weight"), 0.5d),
            JsonProjectionReader.doubleValue(item.get("vector_weight"), 0.5d),
            JsonProjectionReader.intValue(item.get("candidate_top_k"), 20),
            JsonProjectionReader.doubleValue(item.get("similarity_threshold"), 0.0d),
            JsonProjectionReader.booleanValue(item.get("rerank_enabled")),
            JsonProjectionReader.stringValue(item, "rerank_model"),
            JsonProjectionReader.stringValue(item, "fail_policy"),
            item.get("expansion_policy") instanceof Map<?, ?> expansion ? (Map<String, Object>) expansion : Map.of(),
            JsonProjectionReader.intValue(item.get("pack_budget"), 1200),
            JsonProjectionReader.parseInstant(item.get("updated_at")),
            JsonProjectionReader.stringValue(item, "updated_by")
        );
    }

    @Override
    public void upsert(RetrievalProfile profile) {
        throw new UnsupportedOperationException("FileProjectionRetrievalProfileStore does not support upsert");
    }
}

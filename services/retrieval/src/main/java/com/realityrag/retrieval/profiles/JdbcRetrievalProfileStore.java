package com.realityrag.retrieval.profiles;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.retrieval.contracts.RetrievalProfile;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;

public class JdbcRetrievalProfileStore implements RetrievalProfileStore {
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {};

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public JdbcRetrievalProfileStore(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @Override
    public Optional<RetrievalProfile> findByProfileId(String profileId) {
        List<RetrievalProfile> rows = jdbcTemplate.query(
            """
                SELECT profile_id, collection_id, profile_version, profile_hash,
                       bm25_weight, vector_weight, candidate_top_k, similarity_threshold,
                       rerank_enabled, rerank_model, fail_policy, expansion_policy,
                       pack_budget, updated_at, updated_by
                FROM retrieval_profiles
                WHERE profile_id = ? AND enabled = TRUE
                ORDER BY collection_id
                """,
            (rs, rowNum) -> mapRow(rs),
            profileId
        );
        return rows.stream().findFirst();
    }

    @Override
    public Optional<RetrievalProfile> findByProfileId(String profileId, String collectionId) {
        List<RetrievalProfile> rows = jdbcTemplate.query(
            """
                SELECT profile_id, collection_id, profile_version, profile_hash,
                       bm25_weight, vector_weight, candidate_top_k, similarity_threshold,
                       rerank_enabled, rerank_model, fail_policy, expansion_policy,
                       pack_budget, updated_at, updated_by
                FROM retrieval_profiles
                WHERE profile_id = ? AND collection_id = ? AND enabled = TRUE
                """,
            (rs, rowNum) -> mapRow(rs),
            profileId,
            collectionId
        );
        return rows.stream().findFirst()
            .or(() -> findByProfileId(profileId));
    }

    @Override
    public List<RetrievalProfile> findAllEnabled() {
        return jdbcTemplate.query(
            """
                SELECT profile_id, collection_id, profile_version, profile_hash,
                       bm25_weight, vector_weight, candidate_top_k, similarity_threshold,
                       rerank_enabled, rerank_model, fail_policy, expansion_policy,
                       pack_budget, updated_at, updated_by
                FROM retrieval_profiles
                WHERE enabled = TRUE
                ORDER BY profile_id, collection_id
                """,
            (rs, rowNum) -> mapRow(rs)
        );
    }

    @Override
    public void upsert(RetrievalProfile profile) {
        String expansionJson;
        try {
            expansionJson = objectMapper.writeValueAsString(profile.expansionPolicy());
        } catch (Exception e) {
            throw new IllegalStateException("Failed to serialize expansion_policy", e);
        }

        Timestamp now = profile.updatedAt() == null ? Timestamp.from(Instant.now()) : Timestamp.from(profile.updatedAt());

        int updated = jdbcTemplate.update(
            """
                UPDATE retrieval_profiles SET
                    profile_version = ?, profile_hash = ?,
                    bm25_weight = ?, vector_weight = ?, candidate_top_k = ?,
                    similarity_threshold = ?, rerank_enabled = ?, rerank_model = ?,
                    fail_policy = ?, expansion_policy = ?::json, pack_budget = ?,
                    enabled = ?, updated_at = ?, updated_by = ?
                WHERE profile_id = ? AND collection_id = ?
                """,
            profile.profileVersion(),
            profile.profileHash(),
            profile.bm25Weight(),
            profile.vectorWeight(),
            profile.candidateTopK(),
            profile.similarityThreshold(),
            profile.rerankEnabled(),
            profile.rerankModel(),
            profile.failPolicy(),
            expansionJson,
            profile.packBudget(),
            true,
            now,
            profile.updatedBy(),
            profile.profileId(),
            profile.collectionId()
        );

        if (updated == 0) {
            jdbcTemplate.update(
                """
                    INSERT INTO retrieval_profiles (
                        profile_id, collection_id, profile_version, profile_hash,
                        bm25_weight, vector_weight, candidate_top_k, similarity_threshold,
                        rerank_enabled, rerank_model, fail_policy, expansion_policy,
                        pack_budget, enabled, updated_at, updated_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::json, ?, ?, ?, ?)
                    """,
                profile.profileId(),
                profile.collectionId(),
                profile.profileVersion(),
                profile.profileHash(),
                profile.bm25Weight(),
                profile.vectorWeight(),
                profile.candidateTopK(),
                profile.similarityThreshold(),
                profile.rerankEnabled(),
                profile.rerankModel(),
                profile.failPolicy(),
                expansionJson,
                profile.packBudget(),
                true,
                now,
                profile.updatedBy()
            );
        }
    }

    private RetrievalProfile mapRow(ResultSet rs) throws SQLException {
        return new RetrievalProfile(
            rs.getString("profile_id"),
            rs.getString("collection_id"),
            rs.getInt("profile_version"),
            rs.getString("profile_hash"),
            rs.getDouble("bm25_weight"),
            rs.getDouble("vector_weight"),
            rs.getInt("candidate_top_k"),
            rs.getDouble("similarity_threshold"),
            rs.getBoolean("rerank_enabled"),
            rs.getString("rerank_model"),
            rs.getString("fail_policy"),
            parseMap(rs.getString("expansion_policy")),
            rs.getInt("pack_budget"),
            toInstant(rs.getTimestamp("updated_at")),
            rs.getString("updated_by")
        );
    }

    private Map<String, Object> parseMap(String rawJson) throws SQLException {
        if (rawJson == null || rawJson.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(rawJson, MAP_TYPE);
        }
        catch (Exception error) {
            throw new SQLException("Failed to parse retrieval_profiles.expansion_policy", error);
        }
    }

    private Instant toInstant(Timestamp timestamp) {
        return timestamp == null ? Instant.EPOCH : timestamp.toInstant();
    }
}

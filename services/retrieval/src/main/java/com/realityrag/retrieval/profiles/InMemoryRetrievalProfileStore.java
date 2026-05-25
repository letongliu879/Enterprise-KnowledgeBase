package com.realityrag.retrieval.profiles;

import com.realityrag.retrieval.contracts.RetrievalProfile;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

public class InMemoryRetrievalProfileStore implements RetrievalProfileStore {
    private final List<RetrievalProfile> profiles = List.of(
        new RetrievalProfile(
            "ret_default",
            "col_policy",
            3,
            "sha256:ret-default-v3",
            0.55d,
            0.45d,
            20,
            0.2d,
            true,
            "rerank-v1",
            "fail_open",
            java.util.Map.of("adjacent_window", 1),
            1200,
            Instant.parse("2026-05-23T00:00:00Z"),
            "adm_ops_01"
        ),
        new RetrievalProfile(
            "ret_default",
            "col_handbook",
            3,
            "sha256:ret-default-v3",
            0.55d,
            0.45d,
            20,
            0.2d,
            true,
            "rerank-v1",
            "fail_open",
            java.util.Map.of("adjacent_window", 1),
            1200,
            Instant.parse("2026-05-23T00:00:00Z"),
            "adm_ops_01"
        )
    );

    @Override
    public Optional<RetrievalProfile> findByProfileId(String profileId) {
        return profiles.stream().filter(profile -> profile.profileId().equals(profileId)).findFirst();
    }

    @Override
    public Optional<RetrievalProfile> findByProfileId(String profileId, String collectionId) {
        return profiles.stream()
            .filter(profile -> profile.profileId().equals(profileId))
            .filter(profile -> profile.collectionId().equals(collectionId))
            .findFirst()
            .or(() -> findByProfileId(profileId));
    }
}

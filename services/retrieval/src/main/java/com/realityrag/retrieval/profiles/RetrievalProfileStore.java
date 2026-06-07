package com.realityrag.retrieval.profiles;

import com.realityrag.retrieval.contracts.RetrievalProfile;
import java.util.List;
import java.util.Optional;

public interface RetrievalProfileStore {
    Optional<RetrievalProfile> findByProfileId(String profileId);

    Optional<RetrievalProfile> findByProfileId(String profileId, String collectionId);

    List<RetrievalProfile> findAllEnabled();

    void upsert(RetrievalProfile profile);
}

package com.realityrag.retrieval.api;

import com.realityrag.retrieval.contracts.RetrievalProfile;
import com.realityrag.retrieval.contracts.RetrievalProfileProjectionSyncRequest;
import com.realityrag.retrieval.contracts.RetrievalProfileProjectionSyncResponse;
import com.realityrag.retrieval.profiles.RetrievalProfileStore;
import jakarta.validation.Valid;
import java.time.Instant;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RetrievalProfileProjectionSyncController {

    private final RetrievalProfileStore retrievalProfileStore;

    public RetrievalProfileProjectionSyncController(RetrievalProfileStore retrievalProfileStore) {
        this.retrievalProfileStore = retrievalProfileStore;
    }

    @PostMapping("/internal/retrieval-profile-projections/sync")
    public ResponseEntity<RetrievalProfileProjectionSyncResponse> syncProjection(
        @Valid @RequestBody RetrievalProfileProjectionSyncRequest request
    ) {
        var projection = request.payload();
        var collectionId = projection.collectionId() == null || projection.collectionId().isBlank()
            ? "_"
            : projection.collectionId();

        var profile = new RetrievalProfile(
            projection.profileId(),
            collectionId,
            projection.profileVersion(),
            projection.profileHash(),
            projection.bm25Weight(),
            projection.vectorWeight(),
            projection.candidateTopK(),
            projection.similarityThreshold(),
            projection.rerankEnabled(),
            projection.rerankModel(),
            projection.failPolicy(),
            projection.expansionPolicy(),
            projection.packBudget(),
            projection.updatedAt() == null || projection.updatedAt().isBlank()
                ? Instant.now()
                : Instant.parse(projection.updatedAt()),
            projection.updatedBy()
        );

        try {
            retrievalProfileStore.upsert(profile);
            return ResponseEntity.ok(
                new RetrievalProfileProjectionSyncResponse(Instant.now().toString(), true)
            );
        } catch (UnsupportedOperationException e) {
            return ResponseEntity.status(HttpStatus.NOT_IMPLEMENTED)
                .body(new RetrievalProfileProjectionSyncResponse(null, false));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new RetrievalProfileProjectionSyncResponse(null, false));
        }
    }
}

package com.realityrag.retrieval.scope;

import com.realityrag.retrieval.contracts.CollectionRetrievalPlan;
import com.realityrag.retrieval.contracts.RetrievalProfile;
import com.realityrag.retrieval.contracts.RetrieveRequest;
import com.realityrag.retrieval.profiles.RetrievalProfileStore;
import com.realityrag.retrieval.scope.sources.IndexRegistryRecord;
import com.realityrag.retrieval.scope.sources.IndexRegistrySource;
import com.realityrag.retrieval.scope.sources.PublishedDocumentRecord;
import com.realityrag.retrieval.scope.sources.PublishedDocumentSource;
import org.springframework.http.HttpStatus;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

@Component
public class CollectionRetrievalPlanBuilder {
    private final RetrievalProfileStore retrievalProfileStore;
    private final PublishedDocumentSource publishedDocumentSource;
    private final IndexRegistrySource indexRegistrySource;

    public CollectionRetrievalPlanBuilder(
        RetrievalProfileStore retrievalProfileStore,
        PublishedDocumentSource publishedDocumentSource,
        IndexRegistrySource indexRegistrySource
    ) {
        this.retrievalProfileStore = retrievalProfileStore;
        this.publishedDocumentSource = publishedDocumentSource;
        this.indexRegistrySource = indexRegistrySource;
    }

    public List<CollectionRetrievalPlan> build(RetrieveRequest request) {
        return request.collectionScope().stream()
            .map(collectionId -> buildPlan(request, collectionId))
            .toList();
    }

    private CollectionRetrievalPlan buildPlan(RetrieveRequest request, String collectionId) {
        RetrievalProfile profile = retrievalProfileStore.findByProfileId(request.retrievalProfileId(), collectionId)
            .orElseThrow(() -> new ResponseStatusException(
                HttpStatus.BAD_REQUEST,
                "Missing retrieval profile: " + request.retrievalProfileId()));
        IndexRegistryRecord indexRegistry = indexRegistrySource.findActiveIndex(collectionId)
            .orElseThrow(() -> new ResponseStatusException(
                HttpStatus.BAD_REQUEST,
                "Missing active index for collection: " + collectionId));
        List<PublishedDocumentRecord> publishedDocs = publishedDocumentSource.listByCollection(collectionId);

        return new CollectionRetrievalPlan(
            indexRegistry.tenantId(),
            collectionId,
            indexRegistry.indexVersionId(),
            indexRegistry.opensearchIndex(),
            indexRegistry.qdrantCollection(),
            indexRegistry.embeddingModel(),
            indexRegistry.chunkProfileId(),
            profileSnapshot(profile),
            profile.profileId(),
            profile.profileVersion(),
            profile.profileHash(),
            Map.of(
                "principal_id", request.principal().principalId(),
                "permission_fingerprint", buildPermissionFingerprint(request, collectionId)
            ),
            lifecycleFilter(request.includeDeprecated()),
            request.includeDeprecated(),
            allowedDocIds(publishedDocs, request.includeDeprecated()),
            request.filters()
        );
    }

    private String buildPermissionFingerprint(RetrieveRequest request, String collectionId) {
        return "perm:" + request.principal().principalId() + ":" + collectionId;
    }

    private Map<String, Object> lifecycleFilter(boolean includeDeprecated) {
        return Map.of(
            "allowed_states",
            includeDeprecated ? List.of("PUBLISHED", "DEPRECATED") : List.of("PUBLISHED")
        );
    }

    private List<String> allowedDocIds(List<PublishedDocumentRecord> publishedDocs, boolean includeDeprecated) {
        return publishedDocs.stream()
            .filter(doc -> includeDeprecated || "PUBLISHED".equals(doc.publishedDocumentState()))
            .map(PublishedDocumentRecord::finalDocId)
            .distinct()
            .toList();
    }

    private Map<String, Object> profileSnapshot(RetrievalProfile profile) {
        Map<String, Object> snapshot = new LinkedHashMap<>();
        snapshot.put("bm25_weight", profile.bm25Weight());
        snapshot.put("vector_weight", profile.vectorWeight());
        snapshot.put("candidate_top_k", profile.candidateTopK());
        snapshot.put("similarity_threshold", profile.similarityThreshold());
        snapshot.put("rerank_enabled", profile.rerankEnabled());
        snapshot.put("rerank_model", profile.rerankModel());
        snapshot.put("fail_policy", profile.failPolicy());
        snapshot.put("expansion_policy", profile.expansionPolicy());
        snapshot.put("pack_budget", profile.packBudget());
        return snapshot;
    }
}

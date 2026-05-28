package com.realityrag.access.service;

import com.realityrag.access.config.AccessProperties;
import com.realityrag.access.clients.RetrievalClient;
import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.support.AccessException;
import org.springframework.stereotype.Component;

@Component
public class RetrievalProfileSelector {
    private final AccessProperties properties;
    private final RetrievalClient retrievalClient;

    public RetrievalProfileSelector(AccessProperties properties, RetrievalClient retrievalClient) {
        this.properties = properties;
        this.retrievalClient = retrievalClient;
    }

    public String select(ExternalRetrieveRequest request) {
        String explicit = normalize(request.retrievalProfileId());
        String alias = normalize(request.profile());
        if (explicit != null && alias != null && !explicit.equals(alias)) {
            throw new AccessException.InvalidRequest("retrieval_profile_id conflicts with deprecated profile alias");
        }
        if (explicit != null) {
            return requireExisting(explicit);
        }
        if (alias != null) {
            return requireExisting(alias);
        }
        return requireExisting(properties.getDefaultRetrievalProfileId());
    }

    private String normalize(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    private String requireExisting(String profileId) {
        if (!retrievalClient.retrievalProfileExists(profileId)) {
            throw new AccessException.InvalidRequest("Unknown retrieval profile: " + profileId);
        }
        return profileId;
    }
}

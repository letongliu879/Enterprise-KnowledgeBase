package com.realityrag.retrieval.api;

import com.realityrag.retrieval.contracts.RetrievalProfile;
import com.realityrag.retrieval.profiles.RetrievalProfileStore;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@RestController
public class RetrievalProfileController {
    private final RetrievalProfileStore retrievalProfileStore;

    public RetrievalProfileController(RetrievalProfileStore retrievalProfileStore) {
        this.retrievalProfileStore = retrievalProfileStore;
    }

    @GetMapping("/internal/retrieval-profiles")
    public List<String> listProfiles() {
        return retrievalProfileStore.findAllEnabled().stream()
            .map(RetrievalProfile::profileId)
            .distinct()
            .sorted()
            .toList();
    }

    @GetMapping("/internal/retrieval-profiles/{profileId}")
    public RetrievalProfile getProfile(@PathVariable String profileId) {
        return retrievalProfileStore.findByProfileId(profileId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Retrieval profile not found"));
    }
}

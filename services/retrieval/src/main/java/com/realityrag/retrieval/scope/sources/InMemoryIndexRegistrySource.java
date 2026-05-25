package com.realityrag.retrieval.scope.sources;

import java.util.List;
import java.util.Optional;

public class InMemoryIndexRegistrySource implements IndexRegistrySource {
    private final List<IndexRegistryRecord> indexRegistry = List.of(
        new IndexRegistryRecord(
            "col_policy",
            "idxv_col_policy_active",
            "os_tnt_default_col_policy_idxv_col_policy_active",
            "qd_tnt_default_col_policy_idxv_col_policy_active",
            "text-embedding-3-large",
            "chunk_default"
        ),
        new IndexRegistryRecord(
            "col_handbook",
            "idxv_col_handbook_active",
            "os_tnt_default_col_handbook_idxv_col_handbook_active",
            "qd_tnt_default_col_handbook_idxv_col_handbook_active",
            "text-embedding-3-large",
            "chunk_default"
        )
    );

    @Override
    public Optional<IndexRegistryRecord> findActiveIndex(String collectionId) {
        return indexRegistry.stream()
            .filter(record -> record.collectionId().equals(collectionId))
            .findFirst();
    }
}

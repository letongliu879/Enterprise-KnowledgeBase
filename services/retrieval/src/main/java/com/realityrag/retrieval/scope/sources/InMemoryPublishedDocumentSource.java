package com.realityrag.retrieval.scope.sources;

import java.util.List;

public class InMemoryPublishedDocumentSource implements PublishedDocumentSource {
    private final List<PublishedDocumentRecord> publishedDocuments = List.of(
        new PublishedDocumentRecord(
            "col_policy",
            "doc_expense_policy",
            "PUBLISHED",
            "idxv_col_policy_active",
            "internal",
            List.of(),
            List.of("finance")
        ),
        new PublishedDocumentRecord(
            "col_handbook",
            "doc_travel_handbook",
            "PUBLISHED",
            "idxv_col_handbook_active",
            "internal",
            List.of(),
            List.of("finance", "hr")
        ),
        new PublishedDocumentRecord(
            "col_policy",
            "doc_old_expense_policy",
            "DEPRECATED",
            "idxv_col_policy_active",
            "internal",
            List.of(),
            List.of("finance")
        )
    );

    @Override
    public List<PublishedDocumentRecord> listByCollection(String collectionId) {
        return publishedDocuments.stream()
            .filter(record -> record.collectionId().equals(collectionId))
            .toList();
    }
}

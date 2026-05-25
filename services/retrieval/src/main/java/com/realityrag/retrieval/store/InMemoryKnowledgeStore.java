package com.realityrag.retrieval.store;

import com.realityrag.retrieval.contracts.KnowledgeContext;
import java.util.List;

public class InMemoryKnowledgeStore implements KnowledgeStore {
    private final List<IndexedChunk> chunks = List.of(
        new IndexedChunk(
            "col_policy",
            "doc_expense_policy",
            "idxv_col_policy_active",
            "dir_doc_expense_policy_01",
            "chk_doc_expense_policy_idxv_col_policy_active_0001",
            "Approved expenses are reimbursable when they follow the expense policy.",
            "Expense Policy Approved expenses are reimbursable when they follow the expense policy.",
            List.of("Expense Policy"),
            List.of(new KnowledgeContext.PageSpan(1, 1)),
            "PUBLISHED",
            "internal",
            List.of(),
            List.of("finance"),
            java.util.Map.of(
                "collection_id", "col_policy",
                "final_doc_id", "doc_expense_policy",
                "anchor", "page:1:span:0-67"
            ),
            java.util.Map.of()
        ),
        new IndexedChunk(
            "col_handbook",
            "doc_travel_handbook",
            "idxv_col_handbook_active",
            "dir_doc_travel_handbook_02",
            "chk_doc_travel_handbook_idxv_col_handbook_active_0007",
            "Travel reimbursements are reimbursable with manager approval for out-of-policy items.",
            "Travel Handbook Travel reimbursements are reimbursable with manager approval for out-of-policy items.",
            List.of("Travel Handbook", "Reimbursement"),
            List.of(new KnowledgeContext.PageSpan(3, 3)),
            "PUBLISHED",
            "internal",
            List.of(),
            List.of("finance", "hr"),
            java.util.Map.of(
                "collection_id", "col_handbook",
                "final_doc_id", "doc_travel_handbook",
                "anchor", "page:3:span:0-73"
            ),
            java.util.Map.of()
        ),
        new IndexedChunk(
            "col_policy",
            "doc_old_expense_policy",
            "idxv_col_policy_active",
            "dir_doc_old_expense_policy_09",
            "chk_doc_old_expense_policy_idxv_col_policy_active_0012",
            "Deprecated policy version for archived reimbursement limits.",
            "Deprecated expense policy archived reimbursement limits.",
            List.of("Deprecated Expense Policy"),
            List.of(new KnowledgeContext.PageSpan(5, 5)),
            "DEPRECATED",
            "internal",
            List.of(),
            List.of("finance"),
            java.util.Map.of(
                "collection_id", "col_policy",
                "final_doc_id", "doc_old_expense_policy",
                "anchor", "page:5:span:0-55"
            ),
            java.util.Map.of()
        )
    );

    @Override
    public List<IndexedChunk> listChunks(String collectionId) {
        return chunks.stream()
            .filter(chunk -> chunk.collectionId().equals(collectionId))
            .toList();
    }
}

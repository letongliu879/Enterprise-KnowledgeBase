package com.realityrag.retrieval.support;

import javax.sql.DataSource;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Seeds test data into tables that must already exist (created by schema.sql / spring.sql.init).
 * This class does NOT create tables — it only inserts and deletes data.
 */
public final class DbBackedRetrievalTestConfig {
    private DbBackedRetrievalTestConfig() {}

    public static void seed(JdbcTemplate jdbcTemplate) {
        jdbcTemplate.update("DELETE FROM chunk_registry");
        jdbcTemplate.update("DELETE FROM indexed_documents");
        jdbcTemplate.update("DELETE FROM index_versions");
        jdbcTemplate.update("DELETE FROM index_registry");
        jdbcTemplate.update("DELETE FROM published_documents");
        jdbcTemplate.update("DELETE FROM retrieval_profiles");
        jdbcTemplate.update("DELETE FROM run_steps");
        jdbcTemplate.update("DELETE FROM run_traces");

        jdbcTemplate.update(
            """
                INSERT INTO retrieval_profiles (
                    profile_id, collection_id, profile_version, profile_hash, bm25_weight, vector_weight,
                    candidate_top_k, similarity_threshold, rerank_enabled, rerank_model, fail_policy,
                    expansion_policy, pack_budget, enabled, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
            "ret_default",
            "col_policy",
            1,
            "sha256:ret-default-test",
            0.55d,
            0.45d,
            20,
            0.2d,
            true,
            "rerank-v1",
            "fail_closed",
            "{\"adjacent_window\":1}",
            1200,
            true,
            "test"
        );
        jdbcTemplate.update(
            """
                INSERT INTO retrieval_profiles (
                    profile_id, collection_id, profile_version, profile_hash, bm25_weight, vector_weight,
                    candidate_top_k, similarity_threshold, rerank_enabled, rerank_model, fail_policy,
                    expansion_policy, pack_budget, enabled, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
            "ret_default",
            "col_handbook",
            1,
            "sha256:ret-default-test",
            0.55d,
            0.45d,
            20,
            0.2d,
            true,
            "rerank-v1",
            "fail_closed",
            "{\"adjacent_window\":1}",
            1200,
            true,
            "test"
        );

        jdbcTemplate.update(
            """
                INSERT INTO published_documents (
                    published_document_id, final_doc_id, logical_document_id, tenant_id, collection_id, version,
                    source_content_hash, canonical_hash, state, active_index_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
            "pub_doc_policy_01",
            "doc_expense_policy",
            "ld_expense_policy",
            "tnt_default",
            "col_policy",
            1,
            "sha256:doc_expense_policy_src",
            "sha256:doc_expense_policy_canonical",
            "PUBLISHED",
            "idxv_col_policy_active"
        );
        jdbcTemplate.update(
            """
                INSERT INTO published_documents (
                    published_document_id, final_doc_id, logical_document_id, tenant_id, collection_id, version,
                    source_content_hash, canonical_hash, state, active_index_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
            "pub_doc_handbook_01",
            "doc_travel_handbook",
            "ld_travel_handbook",
            "tnt_default",
            "col_handbook",
            1,
            "sha256:doc_travel_handbook_src",
            "sha256:doc_travel_handbook_canonical",
            "PUBLISHED",
            "idxv_col_handbook_active"
        );

        jdbcTemplate.update(
            """
                INSERT INTO index_registry (
                    collection_id, index_version, status, created_at, updated_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
            "col_policy",
            "idxv_col_policy_active",
            "ACTIVE"
        );
        jdbcTemplate.update(
            """
                INSERT INTO index_registry (
                    collection_id, index_version, status, created_at, updated_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
            "col_handbook",
            "idxv_col_handbook_active",
            "ACTIVE"
        );
        jdbcTemplate.update(
            """
                INSERT INTO index_versions (
                    index_version_id, tenant_id, collection_id, status, schema_version, index_profile_id,
                    chunk_profile_id, embedding_model, opensearch_index, qdrant_collection, chunk_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
            "idxv_col_policy_active",
            "tnt_default",
            "col_policy",
            "READY",
            "2026-05-26",
            "ragflow",
            "chunk_default",
            "BAAI/bge-m3",
            "os_col_policy_active",
            "qd_col_policy_active",
            1
        );
        jdbcTemplate.update(
            """
                INSERT INTO index_versions (
                    index_version_id, tenant_id, collection_id, status, schema_version, index_profile_id,
                    chunk_profile_id, embedding_model, opensearch_index, qdrant_collection, chunk_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
            "idxv_col_handbook_active",
            "tnt_default",
            "col_handbook",
            "READY",
            "2026-05-26",
            "ragflow",
            "chunk_default",
            "BAAI/bge-m3",
            "os_col_handbook_active",
            "qd_col_handbook_active",
            1
        );

        jdbcTemplate.update(
            """
                INSERT INTO chunk_registry (
                    chunk_id, tenant_id, collection_id, final_doc_id, index_version_id, available_int, visibility, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
            "chk_doc_expense_policy_idxv_col_policy_active_0001",
            "tnt_default",
            "col_policy",
            "doc_expense_policy",
            "idxv_col_policy_active",
            1,
            "internal",
            "{\"collection_id\":\"col_policy\",\"final_doc_id\":\"doc_expense_policy\",\"index_version_id\":\"idxv_col_policy_active\",\"document_index_revision_id\":\"dir_doc_expense_policy_01\",\"chunk_id\":\"chk_doc_expense_policy_idxv_col_policy_active_0001\",\"display_text\":\"Approved expenses are reimbursable when they follow the expense policy.\",\"vector_text\":\"Expense Policy Approved expenses are reimbursable when they follow the expense policy.\",\"section_path\":[\"Expense Policy\"],\"page_spans\":[{\"page_from\":1,\"page_to\":1}],\"published_document_state\":\"PUBLISHED\",\"visibility\":\"internal\",\"allowed_principal_ids\":[],\"allowed_groups\":[\"finance\"],\"citation_payload\":{\"collection_id\":\"col_policy\",\"final_doc_id\":\"doc_expense_policy\",\"anchor\":\"page:1:span:0-67\"},\"metadata\":{}}"
        );
        jdbcTemplate.update(
            """
                INSERT INTO chunk_registry (
                    chunk_id, tenant_id, collection_id, final_doc_id, index_version_id, available_int, visibility, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
            "chk_doc_expense_policy_idxv_col_policy_old_0001",
            "tnt_default",
            "col_policy",
            "doc_expense_policy",
            "idxv_col_policy_old",
            1,
            "internal",
            "{\"collection_id\":\"col_policy\",\"final_doc_id\":\"doc_expense_policy\",\"index_version_id\":\"idxv_col_policy_old\",\"document_index_revision_id\":\"dir_doc_expense_policy_old\",\"chunk_id\":\"chk_doc_expense_policy_idxv_col_policy_old_0001\",\"display_text\":\"This old index chunk must not be returned.\",\"vector_text\":\"old expense policy chunk\",\"section_path\":[\"Expense Policy\"],\"page_spans\":[{\"page_from\":1,\"page_to\":1}],\"published_document_state\":\"PUBLISHED\",\"visibility\":\"internal\",\"allowed_principal_ids\":[],\"allowed_groups\":[\"finance\"],\"citation_payload\":{},\"metadata\":{}}"
        );
        jdbcTemplate.update(
            """
                INSERT INTO chunk_registry (
                    chunk_id, tenant_id, collection_id, final_doc_id, index_version_id, available_int, visibility, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
            "chk_doc_travel_handbook_idxv_col_handbook_active_0007",
            "tnt_default",
            "col_handbook",
            "doc_travel_handbook",
            "idxv_col_handbook_active",
            1,
            "internal",
            "{\"collection_id\":\"col_handbook\",\"final_doc_id\":\"doc_travel_handbook\",\"index_version_id\":\"idxv_col_handbook_active\",\"document_index_revision_id\":\"dir_doc_travel_handbook_02\",\"chunk_id\":\"chk_doc_travel_handbook_idxv_col_handbook_active_0007\",\"display_text\":\"Travel reimbursements are reimbursable with manager approval for out-of-policy items.\",\"vector_text\":\"Travel Handbook Travel reimbursements are reimbursable with manager approval for out-of-policy items.\",\"section_path\":[\"Travel Handbook\",\"Reimbursement\"],\"page_spans\":[{\"page_from\":3,\"page_to\":3}],\"published_document_state\":\"PUBLISHED\",\"visibility\":\"internal\",\"allowed_principal_ids\":[],\"allowed_groups\":[\"finance\",\"hr\"],\"citation_payload\":{\"collection_id\":\"col_handbook\",\"final_doc_id\":\"doc_travel_handbook\",\"anchor\":\"page:3:span:0-73\"},\"metadata\":{}}"
        );
    }

    public static JdbcTemplate jdbc(DataSource dataSource) {
        return new JdbcTemplate(dataSource);
    }
}

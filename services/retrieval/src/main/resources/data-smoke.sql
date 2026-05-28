-- Smoke-test fixture data for retrieval service PostgreSQL database.
-- NOTE: No retrieval_profiles fixture here — profiles come via
-- /internal/retrieval-profile-projections/sync from admin service.

DELETE FROM chunk_registry;
DELETE FROM indexed_documents;
DELETE FROM index_versions;
DELETE FROM index_registry;
DELETE FROM published_documents;
DELETE FROM retrieval_profiles;
DELETE FROM run_steps;
DELETE FROM run_traces;

-- Ensure default tenant exists for FK constraints (shared with Python services)
INSERT INTO tenants (tenant_id, name) VALUES ('default', 'Default Tenant')
ON CONFLICT (tenant_id) DO NOTHING;

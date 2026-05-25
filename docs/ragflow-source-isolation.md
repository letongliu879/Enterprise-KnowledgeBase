# RAGFlow Source Isolation Map

This repository keeps `upstream/ragflow` as the source fork, but the runtime is being narrowed to an intake-focused workbench.

## Current Runtime White List

Only these backend entry modules should be registered at runtime:

- `upstream/ragflow/api/apps/llm_app.py`
- `upstream/ragflow/api/apps/restful_apis/user_api.py`
- `upstream/ragflow/api/apps/restful_apis/tenant_api.py`
- `upstream/ragflow/api/apps/restful_apis/system_api.py`
- `upstream/ragflow/api/apps/restful_apis/dataset_api.py`
- `upstream/ragflow/api/apps/restful_apis/document_api.py`
- `upstream/ragflow/api/apps/restful_apis/chunk_api.py`
- `upstream/ragflow/api/apps/restful_apis/file_api.py`
- `upstream/ragflow/api/apps/restful_apis/file2document_api.py`
- `upstream/ragflow/api/apps/restful_apis/task_api.py`
- `upstream/ragflow/api/apps/restful_apis/connector_api.py`
- `upstream/ragflow/api/apps/restful_apis/langfuse_api.py`

These modules remain loaded because the current workbench still depends on them:

- `llm_app.py`: dataset creation and model selection still call `/v1/llm/*`.
- `user_api.py`: login, `/users/me`, `/users/me/models`.
- `tenant_api.py`: current settings/team flows still call `/tenants*`.
- `system_api.py`: system config/version/token management.
- `connector_api.py`: data-source ingestion entrypoints remain part of upstream intake UX.
- `langfuse_api.py`: user settings still request Langfuse config.

## Core Intake Workbench

These modules are part of the document intake and chunking path and should be treated as the primary fork surface.

### REST routes

- `dataset_api.py`
- `document_api.py`
- `chunk_api.py`
- `file_api.py`
- `file2document_api.py`
- `task_api.py`

### App services

- `apps/services/dataset_api_service.py`
- `apps/services/document_api_service.py`
- `apps/services/file_api_service.py`

### DB services

- `db/services/knowledgebase_service.py`
- `db/services/document_service.py`
- `db/services/task_service.py`
- `db/services/file_service.py`
- `db/services/file2document_service.py`
- `db/services/doc_metadata_service.py`
- `db/services/pipeline_operation_log_service.py`

## Shared Supporting Infra

These modules are not the intake domain itself, but the current workbench still depends on them.

- `user_api.py`
- `tenant_api.py`
- `system_api.py`
- `connector_api.py`
- `langfuse_api.py`
- `llm_app.py`
- `db/services/user_service.py`
- `db/services/tenant_llm_service.py`
- `db/services/llm_service.py`
- `db/services/connector_service.py`
- `db/services/langfuse_service.py`
- `db/services/api_token_service.py`
- `db/joint_services/tenant_model_service.py`
- `db/joint_services/user_account_service.py`

## Legacy Product Domains

These modules are product domains we are pruning away from the intake fork. They may remain in source temporarily, but they should not be loaded by default and should be candidates for physical relocation later.

### REST routes

- `agent_api.py`
- `bot_api.py`
- `chat_api.py`
- `dify_retrieval_api.py`
- `mcp_api.py`
- `memory_api.py`
- `openai_api.py`
- `plugin_api.py`
- `search_api.py`
- `stats_api.py`

### App modules and services

- `apps/services/canvas_replica_service.py`
- `apps/services/memory_api_service.py`

### DB services

- `db/services/api_service.py` (`API4ConversationService` only after extraction)
- `db/services/canvas_service.py`
- `db/services/chunk_feedback_service.py`
- `db/services/conversation_service.py`
- `db/services/dialog_service.py`
- `db/services/evaluation_service.py`
- `db/services/mcp_server_service.py`
- `db/services/memory_service.py`
- `db/services/search_service.py`
- `db/services/system_settings_service.py`
- `db/services/user_canvas_version.py`
- `db/joint_services/memory_message_service.py`

## Next Cuts

The next backend pruning step should follow this order:

1. Stop importing legacy service modules from any surviving intake/shared route.
2. Move legacy product domains under an explicit `legacy/` or equivalent holding area inside the fork.
3. Replace MySQL and Elasticsearch only after the runtime entry set is stable and the intake data model boundary is clear.

## Storage Replacement Entry Points

The fork now has an explicit runtime port layer at:

- `upstream/ragflow/api/ports/runtime_ports.py`
- `upstream/ragflow/api/ports/__init__.py`

Current ports:

- `doc_store_port`
- `metadata_store_port`
- `task_queue_port`

Current live adopters:

- `apps/restful_apis/system_api.py`
- `db/services/task_service.py`

This is the intended fast path for replacing infrastructure without re-editing every business module first.

Recommended migration order:

1. `task_queue_port`
   Replace Redis-backed queue/cancel/heartbeat behavior first.
2. `doc_store_port`
   Replace chunk index CRUD and retrieval-facing document store operations.
3. `metadata_store_port`
   Replace document metadata index access after document-store behavior is stable.

Recommended next files to switch onto ports:

- `apps/services/dataset_api_service.py`
- `db/services/document_service.py`
- `apps/restful_apis/chunk_api.py`
- `apps/restful_apis/document_api.py`

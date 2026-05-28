# RAGFlow 源码隔离映射

本仓库保留 `upstream/ragflow` 作为源码分叉基础，但运行时正在收缩为面向摄入的工作台。

## 1. 当前运行时白名单

以下后端入口模块应在运行时注册：

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

这些模块继续加载的原因是当前工作台仍依赖它们：

- `llm_app.py`：dataset 创建与模型选择仍调用 `/v1/llm/*`
- `user_api.py`：login、`/users/me`、`/users/me/models`
- `tenant_api.py`：当前设置/团队流程仍调用 `/tenants*`
- `system_api.py`：系统配置/版本/token 管理
- `connector_api.py`：数据源摄入入口仍属于上游 intake UX
- `langfuse_api.py`：用户设置仍请求 Langfuse 配置

## 2. 核心摄入工作台

以下模块属于文档摄入与分块路径，应作为主要分叉面处理。

### REST 路由

- `dataset_api.py`
- `document_api.py`
- `chunk_api.py`
- `file_api.py`
- `file2document_api.py`
- `task_api.py`

### App 服务

- `apps/services/dataset_api_service.py`
- `apps/services/document_api_service.py`
- `apps/services/file_api_service.py`

### DB 服务

- `db/services/knowledgebase_service.py`
- `db/services/document_service.py`
- `db/services/task_service.py`
- `db/services/file_service.py`
- `db/services/file2document_service.py`
- `db/services/doc_metadata_service.py`
- `db/services/pipeline_operation_log_service.py`

## 3. 共享支撑设施

以下模块不属于摄入域本身，但当前工作台仍依赖它们。

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

## 4. 遗留产品域

以下模块是我们正在从摄入分叉中裁剪掉的产品域。它们可能暂时保留在源码中，但默认不应加载，后续应作为物理迁移的候选对象。

### REST 路由

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

### App 模块与服务

- `apps/services/canvas_replica_service.py`
- `apps/services/memory_api_service.py`

### DB 服务

- `db/services/api_service.py`（`API4ConversationService` 在提取后仅保留）
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

## 5. 下一轮裁剪

下一轮后端裁剪应按以下顺序进行：

1. 停止从任何存活的路由中导入遗留服务模块。
2. 将遗留产品域迁移到分叉内明确的 `legacy/` 或等效暂存区。
3. 仅在运行时入口集合稳定且摄入数据模型边界清晰后，再替换 MySQL 和 Elasticsearch。

## 6. 存储替换入口

分叉现在拥有显式的运行时端口层：

- `upstream/ragflow/api/ports/runtime_ports.py`
- `upstream/ragflow/api/ports/__init__.py`

当前端口：

- `doc_store_port`
- `metadata_store_port`
- `task_queue_port`

当前已接入的使用方：

- `apps/restful_apis/system_api.py`
- `db/services/task_service.py`

这是在不先逐个重编每个业务模块的情况下替换基础设施的推荐快速路径。

推荐的迁移顺序：

1. `task_queue_port`
   先替换基于 Redis 的队列/取消/心跳行为。
2. `doc_store_port`
   替换 chunk 索引 CRUD 与面向检索的文档存储操作。
3. `metadata_store_port`
   在文档存储行为稳定后，替换文档元数据索引访问。

推荐下一个切换到端口的文件：

- `apps/services/dataset_api_service.py`
- `db/services/document_service.py`
- `apps/restful_apis/chunk_api.py`
- `apps/restful_apis/document_api.py`

## 7. 与平台服务的关系

`upstream/ragflow` 的解析/分块运行时能力通过 `services/indexing` 接入，而不是直接被外部服务调用。

具体接入方式：

- `services/indexing` 中的 `ParsePreviewRunner` 通过 `RAGFlowAppRuntime` 调用上游解析路径
- `services/indexing` 中的 `IndexJobRunner` 消费 `ParseSnapshot.upstream_chunks` 做正式 chunk 生成
- 平台不直接暴露 `upstream/ragflow` 的 REST 边界给外部调用方
- `upstream/ragflow` 的 `dataset/file/chunk` 对象模型只在解析工作台内部使用，不替代平台的 `collection/final_doc_id` 治理模型

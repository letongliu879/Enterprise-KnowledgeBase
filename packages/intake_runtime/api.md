# intake_runtime 对外接口契约

## Stage 契约 (`stages/`)

### Protocol

| 类型 | 位置 | 说明 |
|------|------|------|
| `StageContext` | `stages/protocol.py:27` | 中心可变的 stage 上下文 dataclass（~30 字段） |
| `PipelineStage` | `stages/protocol.py:66` | Stage 接口 Protocol: `run(ctx) -> ctx` |

### Stage 数据模型

| 模型 | 位置 | 关键字段 |
|------|------|----------|
| `ConversionStageInput` | `schemas.py:19` | `intake_job_id`, `collection_id`, `source_file_path`, `source_hash`, `source_metadata`, `existing_published_doc_id_by_source_hash` |
| `ConversionStageOutput` | `schemas.py:45` | `input_hash`, `result_hash`, `conversion_result`, `quality_report`, `preliminary_doc_id`, `version_conflict`, `dedup_skipped` |
| `ReviewStageInput` | `schemas.py:62` | `intake_job_id`, `collection_id`, `parse_snapshot_id`, `canonical_content`, `quality_report`, `review_model` |
| `ReviewStageOutput` | `schemas.py:77` | `input_hash`, `result_hash`, `agent_review`, `cache_hit` |
| `PublishingStageInput` | `schemas.py:87` | `intake_job_id`, `final_doc_id`, `conversion_result`, `agent_review`, `publish_status` |
| `PublishingStageOutput` | `schemas.py:107` | `input_hash`, `result_hash`, `asset_paths`, `asset_bundle`, `document_persisted` |
| `VersionConflictInfo` | `schemas.py:36` | `logical_document_id`, `existing_version`, `conflict_type` |

### 纯 Stage Executor

| 函数 | 位置 | 说明 |
|------|------|------|
| `run_conversion_stage(input, converters, session, ...) -> output` | `pure_stages.py:53` | 纯转换执行器 |
| `run_review_stage(input, cache, reviewer, ...) -> output` | `pure_stages.py:263` | 纯审核执行器 |
| `run_publishing_stage(input, session, ...) -> output` | `pure_stages.py:421` | 纯发布执行器 |

### Context ↔ DTO 适配器 (`adapters.py`)

| 函数 | 方向 |
|------|------|
| `ctx_to_conversion_input(ctx)` / `conversion_output_to_ctx(ctx, output)` | Context ↔ Conversion |
| `ctx_to_review_input(ctx)` / `review_output_to_ctx(ctx, output)` | Context ↔ Review |
| `ctx_to_publishing_input(ctx)` / `publishing_output_to_ctx(ctx, output)` | Context ↔ Publishing |

### Hash 工具 (`hash_utils.py`)

| 函数 | 说明 |
|------|------|
| `canonical_json(obj) -> str` | 确定性 JSON 序列化 |
| `sha256_hash(data) -> str` | SHA-256 哈希 |
| `compute_input_hash(stage_input) -> str` | 输入 hash（stage + version + 具体字段） |
| `compute_result_hash(stage_output) -> str` | 结果 hash（排除 hash 字段） |

## Stage 运行时 (`stage_runtime.py`)

| 顶层函数 | 说明 |
|----------|------|
| `build_stage_context(session, intake_job_id, ...) -> StageContext` | 加载 repos + 构建 Context |
| `start_stage(ctx, stage_name) -> StageContext` | 创建 task + 获取 lease + 开始 attempt |
| `finish_stage(ctx, output) -> StageContext` | 完成 attempt + 记录 result + 释放 lease |
| `run_conversion(ctx) -> StageContext` | 全流程转换编排 |
| `execute_conversion_task(worker_id, event) -> bool` | 事件驱动转换执行器 |
| `run_review(ctx) -> StageContext` | 全流程审核编排 |
| `execute_review_task(worker_id, event) -> bool` | 事件驱动审核执行器 |
| `run_publishing(ctx) -> StageContext` | 全流程发布编排 |
| `execute_publishing_task(worker_id, event) -> bool` | 事件驱动发布执行器 |

## 转换器 (`converters/`)

| 类型 | 位置 | 说明 |
|------|------|------|
| `BaseConverter` | `converters/base.py:8` | 抽象转换器：`convert()`, `supported_extensions()` |
| `RAGFlowConverter` | `converters/ragflow_converter.py:34` | HTTP 代理到 indexing-service 的实时转换 |

## 代理审核 (`agent_reviewer.py`)

| 类型/函数 | 说明 |
|-----------|------|
| `DeepSeekReviewConfig` | 审核配置 dataclass（base_url, api_key, model, timeout, provider 等） |
| `DeepSeekAgentReviewer` | 两轮审核引擎: `review(content, collection_info, ...) -> AgentReview` |
| `build_deepseek_review_config_from_env()` | 从环境变量构建配置 |
| `get_agent_reviewer() -> DeepSeekAgentReviewer` | 默认审核器工厂 |

### 审核异常

| 异常 | 说明 |
|------|------|
| `AgentReviewConfigurationError` | 配置缺失 |
| `AgentReviewUnavailableError` | 后端不可达 |
| `AgentReviewResponseError` | 响应解析失败 |

## 审核缓存 (`agent_review_cache.py`)

| 类型/函数 | 说明 |
|-----------|------|
| `AgentReviewCache` Protocol | 接口: `get(key)`, `set(key, review, ttl)` |
| `InMemoryAgentReviewCache` | 内存字典实现 |
| `RedisAgentReviewCache` | Redis 实现 |
| `get_agent_review_cache() -> AgentReviewCache` | 单例工厂（env: `AGENT_REVIEW_CACHE_MODE`=memory\|redis） |

## 编排器 (`orchestrator.py`)

| 方法 | 说明 |
|------|------|
| `OrchestratorService(session)` | Job/Task/Attempt 生命周期管理 |
| `OrchestratorService.create_job(...) -> IntakeJob` | 创建 intake job |
| `OrchestratorService.create_stage_task(...) -> StageTask` | 创建 stage task + 发布 `StageTaskRequested` |
| `OrchestratorService.finalize_publishing(...)` | 发布 `StageCompleted` + `PublishCompleted` |
| `OrchestratorService.request_approval(...)` | 发布 `ApprovalRequested` |

## 索引资产构建 (`index_assets.py`)

| 函数 | 说明 |
|------|------|
| `build_index_asset_bundle(...) -> IndexAssetBundle` | 从 conversion_result 构建 ChunkAsset + OpenSearch + Qdrant 记录 |
| `retarget_index_asset_bundle(bundle, new_version) -> IndexAssetBundle` | 修改 bundle 的 index_version |

## 发布持久化 (`publishing_persistence.py`)

| 函数 | 说明 |
|------|------|
| `persist_document_and_policy(ctx) -> tuple[bool, bool]` | 持久化 doc + policy 事实到 DB |

## 发布工具 (`pipeline_utils.py`)

| 函数 | 说明 |
|------|------|
| `build_canonical_metadata(ctx) -> CanonicalMetadata` | 从 StageContext 构建治理元数据 |
| `build_document_asset_paths(collection_id, doc_id) -> dict` | 构建 sidecar asset 路径 |
| `write_json_asset(path, data)` | 写 JSON 到 sidecar 目录 |

## 质量检测 (`quality_utils.py`)

| 函数 | 说明 |
|------|------|
| `detect_garbled_text(text) -> float` | 乱码比例检测 |
| `assess_table_quality(text) -> float` | 表格提取质量评分 |
| `detect_truncation(text) -> bool` | 截断检测启发式 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `INDEXING_SERVICE_URL` | - | RAGFlow 转换服务 URL |
| `DEEPSEEK_API_KEY` | - | 审核 LLM API Key |
| `DEEPSEEK_BASE_URL` | - | 审核 LLM Base URL |
| `DEEPSEEK_MODEL` | - | 审核 LLM 模型名 |
| `AGENT_REVIEW_CACHE_MODE` | memory | `memory` 或 `redis` |
| `REDIS_URL` | redis://localhost:6379/0 | Redis 连接 URL |
| `REALITY_RAG_SIDECAR_DIR` | ./sidecar | Sidecar 资产输出目录 |

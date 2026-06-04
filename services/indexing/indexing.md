# indexing 文档理解与索引构建服务设计

## 1. 定位

`services/indexing` 是本平台唯一正式的 parser/chunker owner。

负责：

- 读取原始文件或受控 source asset
- 执行预解析
- 生成 `ParseSnapshot`
- 提供 chunk preview
- 复用 `ParseSnapshot` 执行正式 chunking
- 生成 embedding
- 写入 lexical/vector index
- 管理 document index revision 与 activate/rollback/cleanup
- 支持发布后 chunk revision 与重新物化

以下职责**不属于** indexing：

- 文档准入
- 审批
- 最终可见性决策
- 文档生命周期治理
- 对外查询 API

核心边界：`indexing` 拥有文档理解真相；`intake-pipeline` 拥有治理与发布真相。

## 2. 边界原则

### 2.1 链路模型

当前正式链路应理解为：

1. 管理员把原始文档提交给 `intake-pipeline`
2. `intake-pipeline` 负责治理
3. `intake-pipeline` 把原始文档和治理结果交给 `indexing`
4. `indexing` 把原始文档交给 `packages/ragflow_runtime`
5. `packages/ragflow_runtime` 只负责解析、分块、结构提取，并把结果返回给 `indexing`
6. `indexing` 把治理字段挂到 chunk、vector 和索引记录上
7. `indexing` 再执行索引写入、版本激活、回滚和清理

必须强调：

- `packages/ragflow_runtime` 不是治理 owner
- `packages/ragflow_runtime` 不负责租户隔离、可见性、访问控制、发布状态
- 治理字段 owner 始终是 `intake-pipeline` 和 `services/indexing`
- `ragflow_runtime` 返回的是解析结果，不是带平台治理的最终索引记录

### 2.2 embedding 执行权与输入语义

这里必须明确区分两件事：

1. `embedding` 由谁执行
2. `embedding` 之前的文本组织规则由谁定义

本项目当前应坚持的边界是：

- `ragflow_runtime` 定义真实的解析语义、chunk 语义以及各 parser 的 embedding 输入组织语义
- `services/indexing` 保留最终 chunk 版本决定权，并执行实际的 embedding 请求与索引写入
- `services/indexing` 通过 `ParserProfile.embedding_text_policy` 驱动 `VectorTextBuilder`，按 parser 类型选择 embedding 输入文本的组织方式

当前已实现的 `embedding_text_policy` 包括：

- `display_text` — 默认，直接使用 chunk 的 `content_with_weight`
- `question_kwd` — QA 文档优先使用 `question_kwd` 列表拼接（如 `qa` parser）
- `display_text_with_authors` — 在 display text 后追加 authors 信息（如 `paper` parser）
- `display_text_with_section_path` — 在 display text 前拼接 `section_path`（如 `manual` parser）

这意味着：

- 是否拼标题
- 是否拼 `section_path`
- 是否拼 `question`
- 是否拼 `authors`
- 是否拼 `important_kwd`
- 是否按 `presentation` / `table` / `paper` / `qa` 等专用 parser 做前处理

这些都应优先对齐上游真实 parser 语义，由 `ParserProfile` 统一驱动，而不是由本地层重新发明。

同时也必须保留：

- `indexing` 可以在 `ParseSnapshot` 之后承接治理字段
- `indexing` 可以在最终入库前接入人工修订或 agent 修订后的 chunk 版本（通过 ChunkRevision 或 pre-publish edit overlay）
- 一旦最终 chunk 版本被修改，`embedding` 由 `indexing` 负责按同一套上游语义重新计算
- embedding API 调用已按 `INDEXING_EMBEDDING_BATCH_SIZE` 分片，保持输出顺序与输入顺序一致

### 2.3 正式输入

`indexing` 的正式输入应是：

- `source_binary_ref`
- `source_file_id`
- `parser_id`（或经由 `ParsePolicyResolver` 自动决策）
- `parse_snapshot_id`
- `governance_overlay_ref`

而不是默认依赖：

- `canonical_md_ref`
- `sanitized_md_ref`

后两者在过渡期可以作为治理辅助资产或审计与人工复核辅助资产，但不能继续定义 parser owner。

### 2.4 解析一次，复用两次

同一份文件的主线应是：

```text
source file
  -> indexing pre-parse
  -> ParseSnapshot
  -> intake/workbench review
  -> publish approved
  -> indexing materialize index from ParseSnapshot
```

这条主线要求：

- 审批前预览与正式索引共享同一份解析快照
- 默认不允许审批前后各跑一套独立解析链

### 2.5 只复用受控的 RAGFlow runtime 子系统

`indexing` 可以直接复用：

- `deepdoc/parser/*`
- `deepdoc/vision/*`
- 布局恢复、结构恢复
- 低层 chunker、metadata、标题切分模块
- `rag.app.*` 中按文档类型划分的解析/切分逻辑
- `rag.flow.*` 中真正属于文档理解的 parser/chunker/runtime 组件
- 表格、图片、演示文稿、简历、问答、书籍、法律文档等专用解析路径

`indexing` 不应直接依赖：

- `api.db.services.*`
- `TaskService`
- `DocumentService`
- Redis 任务宿主
- 上游产品态 dataset/file 生命周期

这些必须通过本项目自己的 runtime/adapters/ports 承接。

约束不是"只能用 DeepDoc"。真正的约束是：

- 只能复用 RAGFlow 中属于文档理解与分块运行时的子系统
- 不能把上游产品宿主层一起搬进来

进一步约束：

- 上述约束不意味着可以在本地重写一套"等价 parser/chunker"来替代上游真实实现。
- `indexing` 不得自建本地解析策略层、本地 chunk 语义层、本地结构抽取编排层来模拟 `RAGFlow`。
- 允许的本地代码只能承担宿主适配职责：承接 `parser_id`、透传/合并上游 `parser_config`、调用上游真实 `chunk()`、冻结 `ParseSnapshot`、执行正式索引物化与可观测性记录。
- 如果某段能力仍然依赖本地推断或本地重组，应明确视为过渡态，而不是目标架构。

## 3. 核心对象

### 3.1 ParseSnapshot

`ParseSnapshot` 是 indexing 的一等产物，由 `ParseSnapshotRecord` 持久化。

当前实际字段（与 `reality_rag_contracts.indexing_models.ParseSnapshotRecord` 一致）：

- `parse_snapshot_id` — 稳定标识，格式为 `pss_{input_hash[:16]}_{parser_id}_{policy_hash}`
- `request_id`
- `source_file_id`
- `tenant_id`
- `collection_id`
- `source_binary_ref`
- `source_filename`
- `source_suffix`
- `parser_id` — 实际使用的上游 parser（如 `naive`、`qa`、`table`）
- `parser_backend` — 当前固定为 `ragflow_app`
- `parser_profile_id` — 生效的 profile 标识，当前格式为 `{document_family}:{parser_id}`
- `chunk_profile_id` — 驱动 chunk 语义的 profile ID，当前与 `parser_id` 对齐
- `document_family` — 文档族（如 `text_document`、`specialized_document`）
- `effective_policy` — 决策原因文本
- `collection_parser_config` — collection 级 parser 配置的冻结副本
- `parser_config` — 最终生效的 parser 配置的冻结副本
- `input_hash` — 源文件内容的 SHA-256
- `preview_text` — 解析后的全文预览
- `upstream_chunks` — 上游 parser 产出的原始 chunk 列表
- `outline` — 文档大纲
- `chunk_preview` — 精简后的 chunk 预览（最多 64 条）
- `document_metadata` — 文档级 metadata
- `warnings` — 解析过程中的警告与决策备注
- `decision_reason`
- `created_at`

它表示：某个输入文件在某个 parser/chunker 配置下得到的一次稳定解析快照。

它不表示：已发布、已生效索引、最终 ACL。

### 3.2 IndexMaterialization

正式建索引的结果至少应包括：

- `index_version_id`
- `document_index_revision_id`
- `parse_snapshot_id`
- `chunk_profile_id`
- `embedding_model`
- `indexed_chunks`
- `index_artifact_refs`
- `activated_at`

### 3.3 GovernanceOverlay

`indexing` 不拥有治理事实，但正式索引时需要消费治理输出。

因此应接收治理覆盖层，例如：

- `final_doc_id`
- `visibility`
- `confirmed_tags`
- `publish_version`
- `governance_overlay_ref`

用途是：给 chunk/document record 挂上最终发布身份，给 retrieval 生成正确的过滤字段。

## 4. 服务主线

### 4.1 预解析主线

```text
ParsePreviewRequested
  -> hint detection
  -> parse policy resolution
  -> load source binary
  -> parser router
  -> structure normalization
  -> preview chunk build
  -> persist ParseSnapshot
  -> ParseSnapshotReady
```

### 4.2 正式索引主线

```text
IndexBuildRequested
  -> load ParseSnapshot
  -> load governance overlay
  -> optional pre-publish chunk edit overlay
  -> final chunk materialization
  -> embedding input assembly (aligned with upstream parser semantics)
  -> embedding
  -> lexical/vector upsert
  -> candidate revision activate (for publish/reindex)
  -> index projection sync to retrieval
  -> retrieval cache purge
  -> IndexReady
```

默认规则：

- 如果 `ParseSnapshot` 可复用，则不得重新跑第二套解析主链
- 只有在 snapshot 失效、profile 变化或显式强制重建时，才允许重新解析
- 正式索引必须加载既有 `ParseSnapshot`，不得回退到 markdown sidecar 或本地 fallback chunker
- 即使 `embedding` 在 `indexing` 执行，embedding 输入文本的组织规则也应继续对齐上游 parser 实际语义
- 如果后续引入人工或 agent 的 chunk 修订层，修订发生在 final materialization 与 embedding 之间，而不是回写成另一套本地 parser 语义

### 4.3 索引版本生命周期

`indexing` 维护索引版本的完整生命周期：

- **BUILDING** -> **READY** -> **ACTIVE** -> **INACTIVE** -> **DISCARDED**
- **ACTIVE** -> **ROLLED_BACK** -> 上一个版本重新 **ACTIVE**

激活（activate）：
- 将目标版本设为 ACTIVE
- 原 ACTIVE 版本设为 INACTIVE
- 更新 indexed_document 状态
- 触发 index projection sync 与 cache purge

回滚（rollback）：
- 将目标版本设为 ROLLED_BACK
- 恢复 `previous_active_index_version_id` 为 ACTIVE
- 更新 indexed_document 状态

清理（cleanup）：
- 仅允许对非 ACTIVE 版本执行
- 删除 chunk registry 记录
- 删除关联 indexed_document
- 版本状态设为 DISCARDED

### 4.4 索引投影同步

`indexing` 在正式物化与激活完成后，通过 `POST /internal/index-projections/sync` 向 `services/retrieval` 同步运行时所需的最小事实集。

同步内容（`IndexProjectionSync`）：

- `index_versions` — 索引版本元数据（schema_version、embedding_model、opensearch_index、qdrant_collection 等）
- `index_registry` — collection 的 active index 映射
- `published_documents` — 文档发布事实（final_doc_id、state、active_index_version 等）
- `chunk_registry` — chunk 全量记录（含 payload_json、available_int、visibility 等）

同步模式：

- `full_replace` — 全量替换某个 collection + index_version 的 chunk 集合

约束：

- 同步端点带幂等控制（`idempotency_key`），重复投递不会重复写入
- retrieval 侧 `chunk_registry` 是派生投影，不是 chunk 真相源；真相源仍在 indexing 持久层
- 激活成功后应立即触发同步，确保 retrieval 运行时可见性与 indexing 侧一致
- sync 与 cache purge 均为 fail-open：retrieval 服务不可达时只记录 warning，不阻断索引物化流程

## 5. 跨服务契约

在进入具体契约前，`indexing` 的解析控制面应固定为三层：

- `DocumentFamily`
- `ParserProfile`
- `ParsePolicyResolver`

其中：

- `DocumentFamily` 负责表达文档属于哪一类解析能力族
- `ParserProfile` 负责表达平台定义的正式解析方案
- `ParsePolicyResolver` 负责把上游默认策略、collection 默认和人工 override 收敛成最终解析决策

建议的 `DocumentFamily` 至少包括：

- `layout_document`
- `table_document`
- `presentation_document`
- `image_document`
- `text_document`
- `specialized_document`

### 5.1 Parser Profile 运行时校验

`POST /internal/parser-profiles/validate` 是 indexing 作为 runtime owner 提供的校验接口。

#### 设计原则

- indexing 只校验 runtime 可执行性，不做 admin 控制面校验
- 不修改 `parser_profiles` 表、不创建 ParseSnapshot、不触发索引 job
- 输出 `canonical_config` 和 `profile_hash`，供 admin 控制面参考

#### 校验项

| 字段 | 规则 |
|---|---|
| `parser_id` | 必须在支持列表中 (`naive`, `presentation`, `paper`, `qa`, `table`, `picture`, `audio`, `email`, `manual`, `resume`) |
| `chunk_token_num` | > 0，且 <= 8192；低于 128 或高于 4096 产生 warning |
| `delimiter` | 必须是字符串 |
| `raptor` | 如有，必须是 dict；`use_raptor` 必须是布尔值 |
| `graphrag` | 如有，必须是 dict；`use_graphrag` 必须是布尔值 |

#### 输出格式

```json
{
  "valid": true,
  "canonical_config": {
    "parser_id": "naive",
    "chunk_token_num": 512,
    "delimiter": "\\n",
    "layout_recognize": "DeepDOC",
    "raptor": {},
    "graphrag": {}
  },
  "profile_hash": "sha256:...",
  "warnings": [],
  "errors": [],
  "runtime_owner": "indexing",
  "validator_version": "indexing-v0.1.0"
}
```

当 `valid=false` 时，`canonical_config` 为 `null`，`profile_hash` 为基于当前配置的占位值。

#### 与 admin 控制面的边界

- admin 负责 ParserProfile CRUD、审批流、版本管理
- indexing 负责校验 profile 在 runtime 是否可执行，并生成 canonical runtime view
- admin 发布前调用此接口；indexing 不主动调用 admin

### 5.2 已注册的 ParserProfile

当前已注册的 `ParserProfile`（静态 registry，位于 `parser_profiles.py`）：

- `naive` — 通用文本 parser，`embedding_text_policy=display_text`
- `presentation` — 幻灯片语义分片，`embedding_text_policy=display_text`
- `table` — 表格感知 parser，`embedding_text_policy=display_text`
- `paper` — 学术论文 parser，`embedding_text_policy=display_text_with_authors`
- `qa` — 问答结构 parser，`embedding_text_policy=question_kwd`
- `picture` — 图片 OCR parser，`embedding_text_policy=display_text`
- `audio` — 音频转录 parser，`embedding_text_policy=display_text`
- `email` — 邮件 parser，`embedding_text_policy=display_text`
- `manual` — 手册/书籍 parser，`embedding_text_policy=display_text_with_section_path`
- `resume` — 简历 parser，`embedding_text_policy=display_text`

规则：

- 平台默认不直接暴露上游内部 parser 名给业务侧；当前 `ParserProfile.profile_id` 与上游 `parser_id` 一一映射
- collection 可配置 `collection_parser_id` 与 `collection_parser_config`
- workbench 人工 override 通过传入 `parser_id` 实现，resolver 会采纳并记录警告
- 正式发布后必须复用 snapshot 内已冻结的解析决策（`parser_id`、`parser_config`、`chunk_profile_id` 均已冻结在 snapshot 中）
- 自动默认继承 RAGFlow 原有的 `get_ragflow_parser()` 解析族默认，平台不自行构造独立解析模式推断逻辑
- 当前实现已经具备：
  - `ParseHintDetector`
  - `ParsePolicyResolver`
  - `ParserProfile` 静态 registry
  - `ParsePreviewRunner`
  - `IndexJobRunner` 基于 `ParseSnapshot` 的正式 materialization
  - `ActivationService` / `RollbackService` / `CleanupService`

### 5.3 ParsePreviewRequested

方向：`intake-pipeline -> indexing`

实际契约字段（`ParsePreviewRequestedCommand`，位于 `preview_contracts.py`）：

- `request_id`
- `tenant_id`
- `collection_id`
- `source_file_id`
- `source_binary_ref`
- `filename`
- `mime_type`
- `parser_id` — 调用方可显式指定上游 parser（如 `qa`），为空则走 resolver 自动决策
- `collection_parser_id` — collection 配置的默认 parser
- `collection_parser_config` — collection 级 parser 配置
- `parser_config` — 调用方可显式传入的 parser 配置（当前仅接受 `parser_id` override，显式 `parser_config` 会被标记为 ignored）
- `content_class_hint`
- `source_system`
- `metadata`
- `trace_id`

说明：

- `parser_id` 手动 override 已被接受（不再关闭）；如果显式传入，resolver 会采纳并记录警告 `manual_parser_override_accepted:{parser_id}`
- `parser_config` 手动 override 当前仍被忽略，记录警告 `manual_parser_config_override_ignored`
- 如果未显式指定 `parser_id`，则由 `ParsePolicyResolver` 按 collection default + 上游 `get_ragflow_parser()` 做保守决策
- resolver 的输出固化到 `ParsePolicy`：
  - `document_family`
  - `parser_id`
  - `parser_backend`
  - `parser_config`
  - `effective_profile_id` — 当前格式为 `{document_family}:{parser_id}`
  - `chunk_profile_id` — 当前与 `parser_id` 对齐
  - `decision_reason`

### 5.4 ParseSnapshotReady

方向：`indexing -> intake-pipeline / workbench-api`

最少字段（`ParseSnapshotReady`，位于 `reality_rag_contracts.models`）：

- `parse_snapshot_id`
- `source_file_id`
- `tenant_id`
- `collection_id`
- `parser_backend`
- `parser_profile_id`
- `preview_text_ref`
- `chunk_preview_ref`
- `warnings`
- `trace_id`

### 5.5 IndexBuildRequested

方向：`publishing-worker / ingestion-worker -> indexing`

实际契约字段（`IndexBuildRequestedCommand`，位于 `reality_rag_contracts.models`）：

- `build_request_id`
- `request_type` — `IndexRequestType` 枚举值：
  - `publish`：build + activate 原子操作
  - `reindex`：build + activate 原子操作
  - `lifecycle_tombstone`：仅构建，不激活
- `tenant_id`
- `collection_id`
- `source_file_id`
- `final_doc_id`
- `document_version`
- `publish_version`
- `visibility`
- `source_binary_ref`
- `parse_snapshot_id`
- `governance_overlay_ref`
- `sanitized_asset_ref`
- `canonical_asset_ref`
- `metadata_ref`
- `quality_report_ref`
- `approval_decision_ref`
- `confirmed_tags`
- `source_metadata`
- `index_profile_id` — 索引后端 profile（如 `ragflow`），不是 parser profile
- `target_index_version_id`
- `chunk_edit_refs` — 预发布 chunk edit 引用列表（当前由 pre-publish edit overlay 机制消费）
- `idempotency_key`
- `trace_id`

说明：

- 正式索引必须加载既有 `ParseSnapshot`，不得回退到 markdown sidecar 或本地 fallback chunker
- `chunk_profile_id` 由 indexing 服务从 snapshot 内解析（`snapshot.chunk_profile_id or snapshot.parser_id or command.index_profile_id`），不再硬编码 `"chunk_default"`
- `request_type="publish"` 或 `"reindex"` 时，indexing 服务在 materialization 成功后自动 activate index version
- `request_type="lifecycle_tombstone"` 时，仅构建不激活

### 5.6 IndexReady

方向：`indexing -> publishing-worker / retrieval`

最少字段：

- `publish_id`
- `reindex_job_id`
- `final_doc_id`
- `collection_id`
- `index_version`
- `document_index_revision_id`
- `parse_snapshot_id`
- `chunk_count`
- `embedding_model_version`
- `searchable_at`
- `trace_id`

## 6. 与 intake-pipeline 的关系

`intake-pipeline` 和 `indexing` 之间的正确分工是：

- intake 负责文件接收、风险审核、审批、发布命令
- indexing 负责解析、快照、chunking、embedding、索引写入

关键约束：

- intake 可以展示 `ParseSnapshot`
- intake 不拥有 parser backend
- indexing 不决定 approve/reject
- publishing 只有在 `IndexReady` 后才能提交最终可检索状态
- intake/workbench 的人工干预对象应是 `parser_id`（如 `naive`、`qa`、`table`），resolver 会将其映射到对应的 `ParserProfile`

## 7. 与 workbench-api 的关系

`workbench-api` 应只是 `indexing` 的受控观察与调试面。

它可暴露：

- ParseSnapshot 查询
- parser/chunker profile 调试
- chunk preview
- 手工复跑 preview
- chunk revision 创建与状态查询

它不应暴露：

- 平台治理真相写入
- 文档生命周期推进
- 发布状态变更

## 8. 运行时实现约束

当前仓库已开始使用 `packages/ragflow_runtime`。

后续实现约束应是：

- 低层 RAGFlow 能力尽量收敛到 `packages/ragflow_runtime`
- `services/indexing` 只依赖受控 runtime 和本地 contracts
- 临时 import alias 只是迁移辅助，不是长期结构

## 9. 配置统一入口

`services/indexing` 的模型与后端配置统一收口在：

- `reality_rag_contracts.config.load_indexing_config()`（被 `indexing_service.config` 重新导出）
- 环境变量或 `.env` 文件

推荐优先使用 `INDEXING_*` 前缀，而不是把环境变量分散在多个模块里：

- `INDEXING_CHAT_API_KEY`
- `INDEXING_CHAT_BASE_URL`
- `INDEXING_CHAT_MODEL`
- `INDEXING_EMBEDDING_API_KEY`
- `INDEXING_EMBEDDING_BASE_URL`
- `INDEXING_EMBEDDING_MODEL`
- `INDEXING_EMBEDDING_BATCH_SIZE`
- `INDEXING_BACKEND_MODE`
- `INDEXING_OPENSEARCH_URL`
- `INDEXING_QDRANT_URL`
- `INDEXING_REQUIRE_LIVE_BACKENDS`

`backends.py` 与 `ragflow_runtime` 宿主兼容层都应从这个统一配置入口读取。

## 10. 可观测性

`services/indexing` 必须具备能支撑后续 parser/profile/chunk 优化的全链路埋点。

当前 indexing 主线至少记录三类对象：

- `RunTrace`
- `RunStep`
- `TraceArtifact`

当前服务内还提供轻量聚合指标出口 `/internal/metrics`，至少聚合：

- parse preview request/success counters
- parser profile 命中 counters
- parse mode 命中 counters
- strategy source counters
- upstream default strategy counters
- materialization request/success counters
- index profile 命中 counters
- preview / materialization duration summaries
- assembled chunk count summaries

### 10.1 Parse Preview Trace

`ParsePreviewRequested -> ParseSnapshot` 当前至少应记录：

- `parse_preview_requested`
- `parse_hint_detected`
- `parse_policy_resolved`
- `parse_snapshot_persisted`

当前至少应挂出的 artifact：

- runtime progress events
- parse snapshot

### 10.2 Index Materialization Trace

`IndexBuildRequested -> chunk materialization` 当前至少应记录：

- `index_build_requested`
- `index_build_job_created`
- `parse_snapshot_loaded`
- `pre_publish_edits_applied`（如有预发布 edit）
- `token_chunks_assembled`
- `index_version_activated`（publish/reindex 时）
- `retrieval_cache_purged`（publish/reindex 时）
- `retrieval_index_projection_synced`（publish/reindex 时）
- `index_chunks_materialized`

当前至少应挂出的 artifact：

- normalized blocks
- chunk records
- indexed_document
- index asset bundle

### 10.3 埋点设计目标

这套埋点必须至少能回答：

- 某份文档为什么命中这个 `parser_profile_id`
- 本次 preview 用了什么 `parse_mode`
- 本次命中的是哪条上游默认策略
- 这次决策来自 manual override、collection default 还是 upstream default
- 生成了什么 `ParseSnapshot`
- 正式索引是否复用了同一份 snapshot
- 最终切成了多少 chunk
- 哪一步最慢、最不稳定、最容易退化

## 11. Chunk Revision Materialization

`ChunkRevision` 是 indexing 对**已发布 chunk 的人工修订**的一等产物。

### 11.1 生命周期

```text
draft -> materializing -> active | failed
```

### 11.2 核心端点

- `POST /internal/chunks/{evidence_id}/revisions`
  - 幂等创建 revision（`idempotency_key` 去重）
  - 验证 base chunk 存在且 tenant/collection 匹配
  - 404：base chunk 不存在
  - 409：tenant/collection 不匹配
  - 200：返回已有 revision（重复 idempotency_key）

- `GET /internal/chunk-revisions/{revision_id}`
  - 读取 revision 状态

- `POST /internal/chunk-revisions/{revision_id}/materialize`
  - 加载 revision 和 base chunk
  - 应用 operation（当前支持 `update` / `delete` / `hide`）
  - 生成新 `ChunkRecord`，重新计算 `chunk_hash`
  - 调用 `build_index_asset_bundle` + `HybridIndexBackend.write_bundle`
  - 旧 chunk `available_int=0`，新 chunk `available_int=1`
  - 更新 revision status -> `active`
  - materialization 失败时 revision status -> `failed`，旧 chunk 不下线

### 11.3 与 workbench 的协作

```text
workbench PATCH /workbench/chunks/{evidence_id}
  -> indexing POST /internal/chunks/{evidence_id}/revisions
     -> PersistentIndexingRepository.create_chunk_revision()
     -> 返回 revision_id + status=draft

workbench POST /workbench/chunk-edits/{chunk_edit_id}/submit
  -> indexing POST /internal/chunks/{evidence_id}/revisions
     -> 使用 chunk_edit_id 作为 idempotency_key
     -> 返回 revision_id + status=draft
```

### 11.4 与 retrieval 的协作

materialization 成功后，indexing 调用 `POST /internal/cache/purge`（retrieval service）清理相关检索缓存。purge 失败记录 warning，不回滚 revision。

## 12. 预发布 Chunk Edit 覆盖与激活后缓存清理

### 12.1 预发布 Chunk Edit 覆盖（Pre-publish Edit Overlay）

在 `IndexBuildRequested` 正式物化前，`IndexJobRunner` 会检查是否存在待应用的预发布 chunk edit。这些 edit 由 `workbench-api` 在审批前创建，状态为 `draft`，在索引物化时被合并到 upstream chunks 上。

**应用时机**：在 `_build_chunks()` 加载 `ParseSnapshot.upstream_chunks` 之后、生成 `ChunkRecord` 之前。

**匹配规则**：按 `revision.base_evidence_id` 匹配 upstream chunk 的 `id` 字段。

**支持的操作**（当前实现）：

| operation | 行为 |
|-----------|------|
| `update` | 覆盖 `content_with_weight`、注入 `__vector_text_override__`、`__section_path_override__`、合并 `metadata` |
| `hide` | 设置 `__hidden__=True`，可选覆盖 `content_with_weight` |
| `delete` | 跳过该 chunk，不生成对应 `ChunkRecord` |

**实现位置**：`IndexJobRunner._apply_pre_publish_edits()`

**关键约束**：
- 只处理 `status="draft"` 的 revision
- fail-open：如果 repository 不支持 `list_chunk_revisions_by_doc`，则返回原始 upstream chunks 不变
- 应用后会记录 `pre_publish_edits_applied` trace step，包含 `applied_count`、`skipped_count`、`original_count`、`result_count`

### 12.2 激活后检索缓存清理（Cache Purge on Activation）

当 `request_type="publish"` 或 `"reindex"` 时，`IndexJobRunner` 在成功激活 index version 后，会自动调用 `services/retrieval` 的 `POST /internal/cache/purge` 清理相关检索缓存。

**调用时机**：`repository.activate(index_version_id)` 成功后立即执行。

**请求体**（`RetrievalCachePurgeRequest`）：

```json
{
  "tenant_id": "tnt_default",
  "collection_id": "col_default",
  "doc_id": "doc_001"
}
```

**实现位置**：`IndexJobRunner._purge_retrieval_cache()`

**关键约束**：
- fail-open：retrieval 服务不可达或返回 4xx/5xx 时只记录 warning，不阻断索引物化流程
- timeout 固定为 10 秒
- 若未配置 `RETRIEVAL_SERVICE_URL` 环境变量，则跳过 purge
- purge 成功后记录 `retrieval_cache_purged` trace step，包含 `purged_count`

### 12.3 与 Chunk Revision Materialization 的协作关系

| 场景 | 覆盖机制 | 缓存清理触发点 |
|------|---------|--------------|
| 预发布 edit（审批前） | `_apply_pre_publish_edits()` 在 build 时合并 | 随 publish/reindex 的 activation 一起触发 |
| 发布后 revision（人工修改已激活 chunk） | `materialize_chunk_revision()` 生成新 chunk、旧 chunk 下线 | materialization 成功后独立调用 purge |

两种场景最终都通过 `POST /internal/cache/purge` 使 retrieval 缓存失效，但调用方和时机不同：
- 预发布 edit 的 purge 由 `IndexJobRunner.accept()` 在 activation 后统一触发
- 发布后 revision 的 purge 由 `PersistentIndexingRepository.materialize_chunk_revision()` 在 materialization 后独立触发

## 13. 服务面（完整端点清单）

### 13.1 对外端点（Inbound）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/internal/parse-previews` | 提交预解析请求（202 Accepted） |
| `GET` | `/internal/parse-snapshots/{parse_snapshot_id}` | 查询 ParseSnapshot |
| `GET` | `/internal/parse-snapshots/{parse_snapshot_id}/chunks` | 分页查询 snapshot upstream chunks（page, page_size） |
| `POST` | `/internal/index-jobs` | 提交正式索引构建请求（202 Accepted） |
| `GET` | `/internal/index-jobs/{job_id}` | 查询索引构建任务状态 |
| `GET` | `/internal/indexed-documents` | 列出已索引文档（支持 collection_id / index_version / final_doc_id 过滤） |
| `POST` | `/internal/index-versions/{index_version_id}/activate` | 激活索引版本 |
| `POST` | `/internal/index-versions/{index_version_id}/rollback` | 回滚到上一个 active 版本 |
| `POST` | `/internal/index-versions/{index_version_id}/cleanup` | 清理废弃索引版本 |
| `GET` | `/internal/index-versions/{index_version_id}` | 查询索引版本元数据 |
| `POST` | `/internal/parser-profiles/validate` | ParserProfile 运行时校验 |
| `POST` | `/internal/chunks/{evidence_id}/revisions` | 创建 chunk revision |
| `GET` | `/internal/chunk-revisions/{revision_id}` | 查询 chunk revision 状态 |
| `POST` | `/internal/chunk-revisions/{revision_id}/materialize` | 执行 chunk revision 物化 |
| `GET` | `/internal/chunks` | 按租户/主体查询 active chunks（tenant_id, principal_id, collection_id, principal_groups） |
| `GET` | `/internal/metrics` | 服务内部聚合指标快照 |

### 13.2 外部调用（Outbound）

| 方向 | 方法 | 路径 | 说明 |
|------|------|------|------|
| indexing -> retrieval | `POST` | `/internal/index-projections/sync` | 同步 index projection（含 full_replace 模式） |
| indexing -> retrieval | `POST` | `/internal/cache/purge` | 清理检索缓存 |

## 附录 A. 当前实施状态

截至 2026-06-04，`services/indexing` 的完成状态如下：

### A.1 已完成的链路

- preview 主链已经直接调用上游 `rag.app.*.chunk()`，不再以本地自造 parser/chunker 语义为核心
- `ParseSnapshot` 现在以 `parser_id / parser_config / upstream_chunks` 为核心输入输出
- `parse_snapshot_id` 已改为基于 `input_hash + parser_id + parser_config_hash` 的稳定标识，同一文件同一配置复用同一份快照
- request 级手动 `parser_id` override 已接受（resolver 采纳并记录警告）；`parser_config` 手动 override 仍被忽略
- `ParsePolicyResolver` / `DocumentFamily` / `ParserProfile` 薄控制面已接入 preview 主链
- `chunk_profile_id` 已从 snapshot 流入 job，不再硬编码 `"chunk_default"`
- embedding 文本组织已由 `ParserProfile.embedding_text_policy` 驱动 `VectorTextBuilder`，替代硬编码的 QA 特例
- embedding API 调用已按 `INDEXING_EMBEDDING_BATCH_SIZE` 分片，保持输出顺序
- `request_type="publish"` / `"reindex"` 显式契约化：build + activate 原子操作；`lifecycle_tombstone` 仅构建不激活
- formal materialization 已经可以从 `upstream_chunks` 生成 chunk records
- chunk records 已可以进一步生成 `IndexAssetBundle`
- 已具备 OpenSearch/Qdrant payload 生成链
- `services/indexing` 内部模型与索引后端配置已经统一收口到 `config.py`（重新导出 `reality_rag_contracts.config`）
- chat 与 embedding 已支持分开配置：chat 可单独指向 DeepSeek；embedding 可单独指向 OpenAI-compatible embedding 服务
- 索引版本生命周期完整：activate / rollback / cleanup 均已实现
- index projection sync 到 retrieval 已集成到 publish/reindex 激活流程

### A.2 已吸收的上游 parser 语义

- `presentation`：slide 级语义已进入正式 materialization；`section_path` 已保留 `Title -> Slide N`；citation anchor 已带 slide chunk 语义
- `table`：table metadata 聚合不再本地重写，已转为受控复用上游 `table_es_metadata`；`field_map` 与 `table_column_names` 已冻结进 snapshot
- `manual`：优先承接上游 `section_paths`，不再本地重造章节路径
- `paper`：`authors`、`important_kwd` 等论文语义已进入 `vector_text` 与 metadata 组织
- `qa`：question 语义已进入 `section_path`、metadata 与 embedding 前文本组织

### A.3 已吸收的上游写入语义

- `insert_chunks()` 对应的通用 doc-store 字段骨架已经进入正式主链
- chunk / bundle / indexed_document 三层关联已经打通
- hidden parent chunk / hidden toc chunk 已可正式落库并受 `available_int` 控制
- 文档级 `IndexedDocument` 已可表达 parser、suffix、metadata、outline、可见/隐藏记录计数
- 上游通用兼容字段如 `kb_id / source_id / removed_kwd / pagerank_fea / chunk_data` 已进入主链或具备稳定映射策略

### A.4 已进入主链的治理入库语义

- `governance_overlay_ref`
- `approval_decision_ref`
- `metadata_ref`

这三份治理资产现在不再只是挂在命令对象上的引用，而是会在正式 materialization 时被实际读取。

当前正式以治理资产内容为准的字段包括：

- `final_doc_id`
- `visibility`
- `confirmed_tags`
- `publish_version`
- `approval decision`

这些治理事实现在已经稳定投影到：

- chunk record
- lexical payload
- vector payload
- OpenSearch body
- Qdrant payload
- `IndexedDocument.document_metadata`

这意味着当前 `indexing` 对治理的处理已经从"附带写入少量治理字段"转变为"将治理资产作为正式索引物化输入的一部分"。

### A.5 已进入持久化 registry 的生命周期对象

- index build job
- active index registry
- indexed document
- parse snapshot
- chunk registry
- index version（含 rollback / cleanup 状态迁移）

这些对象现在已经不再只存在于内存状态里，而是已可落到 shared persistence layer。

### A.6 仍未完全收束的部分

- 当前仍保留少量 service runtime cache 作为进程内加速层
- 但持久化模式下，数据库已经是 lifecycle 真相来源

### A.7 已定但尚未完全吸收的上游语义

- OCR / layout 相关 parser_config：还需要继续承接上游对 `layout_recognize`、OCR、页面级参数的真实控制语义
- `task_executor.embedding()` 与 `insert_chunks()`：通用主链核心字段已经基本吸收；剩余主要是专用链字段与少量特殊后处理的最终取舍，而不是主干缺失

### A.8 已可用的后处理能力

- `auto_keywords`
- `auto_questions`
- `auto_metadata`
- `content_tagging`
- `toc_extraction`

其中三类后处理的当前实现边界：

- `auto_metadata`：已按上游 `task_executor -> gen_metadata -> update_metadata_to` 语义执行；metadata schema 合并优先走上游 `turn2jsonschema`；chunk 级 LLM 输出在文档级合并时，按上游 `update_metadata_to` 规则收敛，而不是本地自造 merge 逻辑
- `content_tagging`：已优先按上游思路执行，先尝试复用检索器分布打标，再走 LLM tagging；如果当前宿主没有完整 retriever/doc-store 支撑，则退化到内容命中补全，保证 preview/materialization 链路可用；因此它当前已经可用，但"完全等价于上游线上 tag 分布效果"仍依赖后续将真实检索器宿主接入完整
- `toc_extraction`：已直接复用上游 `run_toc_from_text`；TOC 输出已保持上游 `level/title/chunk_id` 语义，并在正式 materialization 阶段映射为 hidden toc chunk 与 outline ids；当前如果 LLM TOC 提取失败，仍保留受控宿主推断作为退化路径，目标是保持主链可用而不是重新发明 TOC 体系

这三项当前的状态是：已进入正式 preview / snapshot / materialization 主链；`content_tagging` 的最佳效果仍然依赖真实 doc-store/retriever 宿主接入完整；因此"行为语义已基本对齐"，但"线上效果完全等价"尚未结束。

### A.9 Chunk Revision 实施状态

- **ChunkRevision CRUD + materialization 已实现**
- 支持操作：`update`、`delete`、`hide`
- 支持 pre-publish edit overlay（在 IndexBuildRequested 时合并 draft revision）
- materialization 成功后自动清理 retrieval 缓存
- 旧 chunk 在 materialization 失败时保持可用（fail-safe）

## 附录 B. 字段审计

截至 2026-06-04，`services/indexing` 对上游 `insert/write` 字段的处理原则已经明确：

- 不是为了"字段名一模一样"而机械照搬
- 真正需要保留的是字段背后的检索语义、结构语义、可见性语义和写入语义
- 当前实现优先吸收上游真实会影响效果和行为的字段
- 对只服务于专用链、图谱链或尚未接入子系统的字段，暂不盲目落库

### B.1 已吸收的核心写入字段

当前已经正式进入 chunk record / OpenSearch / Qdrant payload 的字段包括：

**文本与分词字段**

- `content_with_weight`
- `content_ltks`
- `content_sm_ltks`
- `docnm_kwd`
- `title_tks`
- `title_sm_tks`
- `important_kwd`
- `important_tks`
- `question_kwd`
- `question_tks`
- `authors_tks`
- `authors_sm_tks`

**标签字段**

- `tag_kwd`
- `tag_feas`

**结构与定位字段**

- `img_id`
- `mom_id`
- `position_int`
- `page_num_int`
- `top_int`
- `row_id` 目前作为 citation/source block 辅助字段透传

**可见性与写入控制字段**

- `available_int`
- `kb_id`
- `doc_id`
- `final_doc_id`
- `index_version_id`
- `document_index_revision_id`
- `indexed_document_id`

**兼容与映射字段**

- `source_id`
- `pagerank_fea`
- `chunk_data`
- `removed_kwd`

**时间字段**

- `create_time`
- `create_timestamp_flt`

这些字段已经不只是存在于内存对象，而是已经进入：

- `ChunkRecord`
- `IndexAssetBundle`
- OpenSearch body
- Qdrant payload
- `IndexedDocument` 关联链

### B.2 已吸收的文档级字段

当前已经正式进入 `IndexedDocument` / `IndexAssetBundle` 顶层的文档级字段包括：

- `parser_id`
- `source_suffix`
- `chunk_count`
- `visible_chunk_count`
- `hidden_chunk_count`
- `has_toc_chunk`
- `has_parent_chunk`
- `document_metadata`
- `outline`

这意味着当前系统已经能在文档级回答：

- 这份索引由哪个 parser 产生
- 原文件是什么后缀
- 一共写了多少记录
- 有多少隐藏辅助记录
- 是否存在 TOC / parent hidden chunk
- 文档级 metadata 和 outline 是什么

### B.3 暂未吸收但已识别的上游字段

以下字段目前没有作为通用企业知识库 indexing 主链的一部分正式落库，但已作为兼容字段支持透传：

- `kb_id`：现已作为兼容字段落库，当前稳定映射到平台 `collection_id`
- `pagerank_fea`：现已支持从 `source_metadata` 透传，当前还没有形成完整的平台排序策略 owner
- `source_id`：现已作为兼容字段落库，当前稳定映射到 `source_file_id`
- `chunk_data`：现已支持原样透传，但当前只有上游 chunk 本身携带该结构时才会落库
- `removed_kwd`：现已作为兼容字段落库，当前平台删除/失活真相仍由 `available_int` 与版本生命周期控制

### B.4 专用链字段暂不纳入通用 indexing 主链

以下字段主要属于 GraphRAG / graph entity / RAPTOR 等专用链，当前不应混入通用企业知识库主链：

- `knowledge_graph_kwd`
- `entity_kwd`
- `entity_type_kwd`
- `from_entity_kwd`
- `to_entity_kwd`
- `weight_int`
- `weight_flt`
- `entities_kwd`
- `rank_flt`
- `raptor_kwd`
- `raptor_layer_int`

这些字段不是"不重要"，而是：

- 它们属于上游专用 indexing 子系统
- 当前企业知识库主链还没有把 GraphRAG / RAPTOR 完整接进来
- 在未接入完整子系统前，不应把它们半截落库成"看起来像支持、实际上没有真正链路"的状态

### B.5 字段策略小结

当前字段策略不是追求表面一致，而是优先保证上游真实行为字段已经进入正式索引主链；对专用链字段保持识别但不乱落库。

下一步优先级：

1. 对上游 `insert_chunks()` 与 doc-store schema 再做最后一轮逐项核对，确认通用主链无实质缺口
2. 明确 GraphRAG / RAPTOR / entity / table-structure 专用字段是否进入后续子系统，而不是混入通用主链
3. 继续做实 `auto_metadata`
4. 继续做实 `content_tagging`
5. 继续做实 `toc_extraction`
6. 然后再进入完整 index update / activate / rollback / cleanup

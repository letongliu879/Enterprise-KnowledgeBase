# ParseSnapshot 架构

## 1. 目的

这份文档固定一条新的边界：

- `indexing` 是正式 parser/chunker owner
- `intake-pipeline` 是治理/审批 owner
- 审批前预览不再依赖 intake 自己维护第二套解析主链

为此，引入一个新的中间对象：`ParseSnapshot`。

## 2. 为什么需要 ParseSnapshot

如果没有 `ParseSnapshot`，系统很容易退化成：

```text
source file
  -> intake 先用轻量转换理解一次
  -> indexing 再用 RAGFlow runtime 子系统理解一次
```

这会造成：

- parser owner 不清
- 双重解析
- workbench 预览和最终索引不同源
- RAGFlow 多解析子系统被前置 markdown 截流

`ParseSnapshot` 的目标是：

```text
source file
  -> indexing 解析一次
  -> intake / workbench / review 使用同一份结果
  -> indexing 正式建索引时继续复用
```

补充约束：

- 这里的"解析一次"指的是承接上游 `RAGFlow` 真实解析链一次，而不是本地先重写一套解析语义再冻结结果。
- `ParseSnapshot` 冻结的应该是上游真实 `parser_id + parser_config + chunk/structure` 结果，而不是平台自创的中间解释层结果。

## 3. 新的全链路

```text
source file
  -> intake-pipeline 接收与治理编排
  -> indexing 预解析
  -> ParseSnapshotReady
  -> intake / workbench / review
  -> approval / publish decision
  -> IndexBuildRequested
  -> indexing 正式索引构建
  -> IndexReady
  -> publishing domain 激活 published_documents.active_index_version
```

## 4. 核心对象

### 4.1 SourceAsset

owner：`intake-pipeline`

字段至少包括：

- `source_file_id`
- `tenant_id`
- `collection_id`
- `object_ref`
- `filename`
- `mime_type`
- `content_hash`

### 4.2 ParseSnapshot

owner：`indexing`

**契约模型**（`reality_rag_contracts.ParseSnapshot`）字段：

- `parse_snapshot_id`
- `source_file_id`
- `tenant_id`
- `collection_id`
- `parser_backend`
- `parser_profile_id`
- `input_hash`
- `preview_text_ref`
- `normalized_blocks_ref`
- `outline_ref`
- `chunk_preview_ref`
- `warnings`
- `created_at`

**实际持久化模型**（`ParseSnapshotModel` / `ParseSnapshotRecord`）字段：

- `parse_snapshot_id`
- `request_id`
- `tenant_id`
- `collection_id`
- `source_file_id`
- `source_binary_ref`
- `source_filename`
- `source_suffix`
- `parser_id`
- `parser_backend`
- `collection_parser_config`
- `parser_config`
- `input_hash`
- `preview_text`
- `upstream_chunks`
- `outline`
- `document_metadata`
- `chunk_preview`
- `warnings`
- `decision_reason`
- `created_at`

说明：

- 契约模型使用 `_ref` 语义，是因为跨服务通信时推荐传递引用而不是全文。
- 实际持久化时，`preview_text`、`upstream_chunks`、`outline`、`document_metadata`、`chunk_preview` 等字段直接以 JSON / Text 形式存入 PostgreSQL `parse_snapshots` 表。
- 它表示某份文件在某套 parser/chunker 配置下的解析快照。
- 它不是正式索引结果，也不等于已发布内容。

### 4.3 GovernanceDecision

owner：`intake-pipeline`

字段至少包括：

- `final_doc_id`
- `visibility`
- `confirmed_tags`
- `approval_decision`
- `publish_version`
- `governance_overlay_ref`

### 4.4 IndexMaterialization

owner：`indexing`

字段至少包括：

- `index_version_id`
- `document_index_revision_id`
- `indexed_chunks`
- `document_toc`
- `embedding_model`
- `chunk_profile_id`

## 5. 新边界

### 5.1 intake-pipeline

只负责：

- 文件接收
- 扫描、去重、治理编排
- 审批
- 生命周期
- 发布命令

不负责：

- 正式 parser owner
- 正式 chunk owner
- embedding owner

### 5.2 indexing

只负责：

- 预解析
- ParseSnapshot
- chunk preview
- 正式 chunking
- embedding
- 索引写入
- activate / rollback

当前已实现：

- `ParsePreviewRunner` 执行真实上游 `rag.app.*.chunk()` 路径
- `ParseSnapshot` 冻结 `parser_id`、`parser_config`、`upstream_chunks`、`outline`、`document_metadata`
- 请求级手动 parser override 不再作为执行真相
- 正式物化已消费 `ParseSnapshot.upstream_chunks`
- chunk records 可转换为 `IndexAssetBundle` 及 OpenSearch/Qdrant payload
- `auto_keywords`、`auto_questions` 后处理路径已工作
- `IndexJobRunner` 负责完整索引构建流程
- `ActivationService`、`RollbackService`、`CleanupService` 管理索引版本生命周期

尚未高质量完成：

- `auto_metadata` — 已稳定但不 consistently 产出高质量结果
- `content_tagging` — 已稳定但不 consistently 产出高质量结果
- `toc_extraction` — 已稳定但不 consistently 产出高质量结果

### 5.3 workbench

只负责：

- ParseSnapshot 展示
- 参数调试
- chunk 预览
- 人工确认

不负责：

- 治理真相
- 生命周期真相

## 6. RAGFlow runtime 的定位

这里的正式解析能力不应被缩写成只有 `DeepDoc`。

`indexing` 真正应承接的是受控的 `RAGFlow runtime` 子系统，例如：

- `deepdoc/parser/*` 和 `deepdoc/vision/*`
- `rag.app.*` 中按文档类型拆分的解析/切分路径
- `rag.flow.*` 中属于 parser/chunker 的运行时组件

不能继续采用的旧做法是：

- 让 intake 先把原文件降成 markdown/text
- 再让 indexing 只能消费这份降级结果

那会把 RAGFlow 面向 RAG 设计的多解析路径提前截断。

## 7. 新契约

### 7.1 ParsePreviewRequested

方向：`intake-pipeline -> indexing`

**契约模型**字段（`ParsePreviewRequested`）：

- `request_id`
- `source_file_id`
- `tenant_id`
- `collection_id`
- `source_binary_ref`
- `filename`
- `mime_type`
- `parser_profile_id`
- `trace_id`

**实际命令模型**字段（`ParsePreviewRequestedCommand`）：

- `request_id`
- `tenant_id`
- `collection_id`
- `source_file_id`
- `source_binary_ref`
- `filename`
- `mime_type`
- `parser_id`（可选，手动覆盖）
- `collection_parser_id`（collection 默认 parser）
- `collection_parser_config`
- `parser_config`
- `content_class_hint`
- `source_system`
- `metadata`
- `trace_id`

补充规则：

- `parser_profile_id` / `collection_parser_id` 是平台控制面字段，不是上游内部实现细节名。
- 如果请求没有显式指定 parser，则由 indexing 内部的解析策略按 RAGFlow 原有默认解析族做保守决策，平台只做封装与记录。
- 一旦生成 `ParseSnapshot`，本次解析决策必须被冻结并被后续正式索引复用。
- 手动 parser override 当前会被忽略并记录警告。

### 7.2 ParseSnapshotReady

方向：`indexing -> intake-pipeline / workbench`

**契约模型**字段：

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

**实际运行时**通过 `ParsePreviewAccepted` 返回：

- `request_id`
- `source_file_id`
- `parse_snapshot_id`
- `parser_id`
- `decision_reason`
- `preview_text_ref`
- `chunk_preview_ref`
- `warnings`
- `trace_id`

### 7.3 IndexBuildRequested

方向：`publishing-worker -> indexing`

**契约模型**字段：

- `source_binary_ref`
- `parse_snapshot_id`
- `governance_overlay_ref`
- `final_doc_id`
- `publish_version`
- `index_profile_id`
- `trace_id`

**实际命令模型**字段（`IndexBuildRequestedCommand`）：

- `build_request_id`
- `request_type`（`publish` | `reindex` | `lifecycle_tombstone`）
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
- `index_profile_id`
- `target_index_version_id`
- `idempotency_key`
- `trace_id`

规则：

- `parse_snapshot_id` 是正式索引构建的主输入之一。
- 默认情况下，indexing 复用 ParseSnapshot，不重新走第二套独立解析主链。

## 8. 过渡约束

当前仓库仍有 `canonical_md_ref` / `sanitized_md_ref` 一类字段。

在过渡期它们可以继续存在，但必须降格理解：

- 只是治理侧辅助资产
- 只是 fallback 输入
- 不是 parser owner 真相

禁止继续默认假设：

- "intake 先解析成 markdown，indexing 再消费 markdown" 就是最终态

## 9. 当前实现状态

截至 2026-05-26：

- `services/indexing` preview 已执行真实上游 `rag.app.*.chunk()` 路径
- `ParseSnapshot` 已冻结 `parser_id`、`parser_config`、`upstream_chunks`、`outline`、`document_metadata`
- 请求级手动 parser override 不再作为执行真相
- 正式物化已消费 `ParseSnapshot.upstream_chunks`
- chunk records 可转换为 `IndexAssetBundle` 及 OpenSearch/Qdrant payload
- `IndexJobRunner` 负责完整索引构建流程（chunk 生成、embedding text 构建、registry 写入、backend 写入、activation）
- `ActivationService`、`RollbackService`、`CleanupService` 管理索引版本生命周期

已工作的后处理路径：

- `auto_keywords`
- `auto_questions`

尚未高质量完成：

- `auto_metadata` — 已稳定，但无法 consistently 产出高质量结果
- `content_tagging` — 已稳定，但无法 consistently 产出高质量结果
- `toc_extraction` — 已稳定，但无法 consistently 产出高质量结果

这三条路径现已足够稳定，不会破坏主流程，但仍应视为未完成。

## 10. 一句话

`ParseSnapshot` 的意义，是让 `indexing` 成为正式解析 owner，同时让 `intake-pipeline` 继续拥有审批与发布 owner，而不是让两边各自维护一套文档理解主链。

# indexing — 文档解析与索引构建服务

## 定位
indexing 是平台唯一正式的 parser/chunker owner，负责从原始文件到索引的全链路。

**不做的事**：文档准入、审批、最终可见性决策、文档生命周期治理、对外查询 API。

## 边界原则
- `packages/ragflow_runtime` 只负责解析分块，不负责治理、租户隔离、可见性
- 治理字段 owner 始终是 intake-pipeline 和 indexing
- indexing 保留最终 chunk 版本决定权，并执行 embedding 请求与索引写入
- 正式索引必须加载既有 ParseSnapshot，不得回退到 markdown sidecar 或本地 fallback chunker
- `ParsePreviewRequested` 中 `parser_id` override 已被接受（resolver 采纳并记录 `manual_parser_override_accepted:{id}`），但 `parser_config` override 仍被忽略（记录 `manual_parser_config_override_ignored`）

## 核心数据流
```
预解析: ParsePreviewRequested -> ParseHintDetector -> ParsePolicyResolver
  -> RAGFlowAppRuntime.build_preview() -> UpstreamChunkOrchestrator -> ParseSnapshot

正式索引: IndexBuildRequested -> load ParseSnapshot -> load governance overlay
  -> _apply_pre_publish_edits (合并 draft revision) -> chunk materialization
  -> embedding (按 embedding_text_policy 分片) -> HybridIndexBackend.write_bundle
  -> [publish/reindex] activate -> sync projection -> cache purge (fail-open)
  -> [lifecycle_tombstone] 仅构建不激活
```

## 关键对象
- `ParseSnapshot`：一次解析快照（一等产物），由 `ParseSnapshotRecord` 持久化
- `IndexVersionRecord`：索引版本，生命周期 BUILDING -> READY -> ACTIVE -> INACTIVE -> DISCARDED
- `ChunkRecord`：最终的索引 chunk 记录，包含 lexical_payload / vector_payload / metadata
- `ChunkRevisionRecord`：发布后人工修订，operation = update|delete|hide，status = draft|materializing|active|failed
- `IndexAssetBundle`：写入后端前的组装产物，同时包含 ChunkAsset / OpenSearch / Qdrant 三类记录

## Parser 特殊语义（测试中验证过的行为）
- **presentation**: section_path = `[title, "Slide N"]`, citation.anchor = `"slide:N-M:chunk:N"`, page_kind = "slide", chunk_type = "mixed"（有图的 slide）
- **paper**: metadata.authors = authors_tks, metadata.important_kwd = import_kwd, embedding 用 `display_text_with_authors` 策略
- **manual**: 优先读取上游 `section_paths` 列表，第一个元素与 title 不同时拼接；embeddding 用 `display_text_with_section_path`
- **qa**: section_path = `[title, first_question_kwd]`, embedding 用 `question_kwd` 策略（直接拼接 question 列表），chunk_type = "mixed"（有图的 QA）
- **table**: doc_metadata 聚合上游 table 列值（name_tks/raw, dept_tks/raw 等）
- **naive**: 当 `toc_extraction=True` 时生成 hidden toc chunk

## 治理覆盖逻辑（按优先级）
```
final_doc_id: overlay.final_doc_id > command.final_doc_id
visibility:   overlay.visibility > source_metadata.visibility > command.visibility > "internal"
confirmed_tags: approval.confirmed_tags > overlay.confirmed_tags > command.confirmed_tags > []
publish_version: overlay.publish_version > command.publish_version
published_document_state: approval.decision == "approve" -> "PUBLISHED" | "reject" -> "REJECTED"
```

## invisible chunk 的生成规则
- **parent chunk** (available_int=0): 当 upstream chunk 有 `mom`/`mom_with_weight` 字段时生成
- **TOC chunk** (available_int=0): 当 `snapshot.document_metadata.outline` 存在时生成
- **hidden chunk** (available_int=0): pre-publish edit operation="hide" 时生成

## 约束
- 不得自建本地 parser/chunker 来替代上游 RAGFlow 实现
- 解析链必须直接承接上游 `ragflow_runtime.rag_app.{parser_id}.chunk()`
- ParseSnapshot 可复用时，不得重新跑解析主链
- 嵌入层文本组织由 `ParserProfile.embedding_text_policy` 驱动，不是硬编码
- 检索投影同步 (index projection sync) + 缓存清理 (cache purge) 均为 fail-open
- 预发布 edit 只处理 `status="draft"` 的 revision，fail-open（repository 不支持 list_revisions 时跳过）
- embedding 输出顺序与输入顺序一致（按 batch 分片调用）
- 配置前缀 `INDEXING_*`，统一入口 `indexing_service.config`（重新导出 `reality_rag_contracts.config`）

# indexing 文档理解与索引构建服务设计

## 1. 定位

`services/indexing` 是本平台唯一正式的 parser/chunker owner。

它负责：

- 读取原始文件或受控 source asset
- 执行预解析
- 生成 `ParseSnapshot`
- 提供 chunk preview
- 复用 `ParseSnapshot` 执行正式 chunking
- 生成 embedding
- 写入 lexical/vector index
- 管理 document index revision 与 activate/rollback

它不负责：

- 文档准入
- 审批
- 最终可见性决策
- 文档生命周期治理
- 对外查询 API

一句话：

- `indexing` 拥有文档理解真相
- `intake-pipeline` 拥有治理与发布真相

## 2. 边界原则

### 2.0 intake -> indexing -> ragflow_runtime -> indexing

当前正式链路应理解为：

1. 管理员把原始文档提交给 `intake`
2. `intake` 负责治理
3. `intake` 把原始文档和治理结果交给 `indexing`
4. `indexing` 把原始文档交给 `packages/ragflow_runtime`
5. `packages/ragflow_runtime` 只负责解析、分块、结构提取，并把结果返回给 `indexing`
6. `indexing` 把治理字段挂到 chunk、vector 和索引记录上
7. `indexing` 再执行索引写入、版本激活、回滚和清理

必须强调：

- `packages/ragflow_runtime` 不是治理 owner
- `packages/ragflow_runtime` 不负责租户隔离、可见性、访问控制、发布状态
- 治理字段 owner 始终是 `intake` 和 `services/indexing`
- `ragflow_runtime` 返回的是解析结果，不是带平台治理的最终索引记录

一句话：

- `ragflow_runtime` 负责理解文档
- `indexing` 负责把解析结果治理化并入库

### 2.0.1 embedding 执行权与 embedding 输入语义

这里必须明确区分两件事：

1. `embedding` 由谁执行
2. `embedding` 之前的文本组织规则由谁定义

本项目当前应坚持的边界是：

- `ragflow_runtime` 定义真实的解析语义、chunk 语义以及各 parser 的 embedding 输入组织语义
- `services/indexing` 保留最终 chunk 版本决定权，并执行实际的 embedding 请求与索引写入

这意味着：

- 是否拼标题
- 是否拼 `section_path`
- 是否拼 `question`
- 是否拼 `authors`
- 是否拼 `important_kwd`
- 是否按 `presentation` / `table` / `paper` / `qa` 等专用 parser 做前处理

这些都应优先对齐上游真实 parser 语义，而不是由本地层重新发明。

同时也必须保留：

- `indexing` 可以在 `ParseSnapshot` 之后承接治理字段
- `indexing` 可以在最终入库前接入人工修订或 agent 修订后的 chunk 版本
- 一旦最终 chunk 版本被修改，`embedding` 由 `indexing` 负责按同一套上游语义重新计算

一句话：

- 上游定义 embedding 的“配方”
- `indexing` 掌握最终版本和“下锅”执行权

### 2.1 正式输入不是 intake markdown

`indexing` 的正式输入应是：

- `source_binary_ref`
- `source_file_id`
- `parser_profile_id`
- `parse_snapshot_id`
- `governance_overlay_ref`

而不是默认依赖：

- `canonical_md_ref`
- `sanitized_md_ref`

后两者在过渡期可以作为：

- 治理辅助资产
- 审计与人工复核辅助资产

但不能继续定义 parser owner。

### 2.2 Parse once, reuse twice

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

### 2.3 只复用受控的 RAGFlow runtime 子系统

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

约束不是“只能用 DeepDoc”。

真正的约束是：

- 只能复用 RAGFlow 中属于文档理解与分块运行时的子系统
- 不能把上游产品宿主层一起搬进来

进一步约束：

- 上述约束不意味着可以在本地重写一套“等价 parser/chunker”来替代上游真实实现。
- `indexing` 不得自建本地解析策略层、本地 chunk 语义层、本地结构抽取编排层来模拟 `RAGFlow`。
- 允许的本地代码只能承担宿主适配职责：承接 `parser_id`、透传/合并上游 `parser_config`、调用上游真实 `chunk()`、冻结 `ParseSnapshot`、执行正式索引物化与可观测性记录。
- 如果某段能力仍然依赖本地推断或本地重组，应明确视为过渡态，而不是目标架构。

## 3. 核心对象

### 3.1 `ParseSnapshot`

`ParseSnapshot` 是 indexing 的一等产物。

最少应包含：

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

它表示：

- 某个输入文件
- 在某个 parser/chunker 配置下
- 得到的一次稳定解析快照

它不表示：

- 已发布
- 已生效索引
- 最终 ACL

### 3.2 `IndexMaterialization`

正式建索引的结果至少应包括：

- `index_version_id`
- `document_index_revision_id`
- `parse_snapshot_id`
- `chunk_profile_id`
- `embedding_model`
- `indexed_chunks`
- `index_artifact_refs`
- `activated_at`

### 3.3 `GovernanceOverlay`

`indexing` 不拥有治理事实，但正式索引时需要消费治理输出。

因此应接收治理覆盖层，例如：

- `final_doc_id`
- `visibility`
- `confirmed_tags`
- `publish_version`
- `governance_overlay_ref`

用途是：

- 给 chunk/document record 挂上最终发布身份
- 给 retrieval 生成正确的过滤字段

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
  -> optional human/agent chunk revision
  -> final chunk materialization
  -> embedding input assembly (aligned with upstream parser semantics)
  -> embedding
  -> lexical/vector upsert
  -> candidate revision activate
  -> IndexReady
```

默认规则：

- 如果 `ParseSnapshot` 可复用，则不得重新跑第二套解析主链
- 只有在 snapshot 失效、profile 变化或显式强制重建时，才允许重新解析
- 正式索引必须加载既有 `ParseSnapshot`，不得回退到 markdown sidecar 或本地 fallback chunker
- 即使 `embedding` 在 `indexing` 执行，embedding 输入文本的组织规则也应继续对齐上游 parser 实际语义
- 如果后续引入人工或 agent 的 chunk 修订层，修订发生在 final materialization 与 embedding 之间，而不是回写成另一套本地 parser 语义

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

建议的 `ParserProfile` 思路至少包括：

- `layout_general`
- `layout_scanned_ocr`
- `paper_layout`
- `table_general`
- `presentation_general`
- `image_general`
- `text_general`
- `resume_structured`
- `qa_structured`

规则：

- 平台默认不直接暴露上游内部 parser 名给业务侧
- collection 只配置 `default_parser_profile_id`
- workbench 人工 override 也只改 `parser_profile_id`
- 正式发布后必须复用 snapshot 内已冻结的解析决策
- 自动默认应尽量继承 RAGFlow 原有的解析族默认，而不是平台自己发明一套新的专用模式猜测
- 当前实现已经具备：
  - `ParseHintDetector`
  - `ParsePolicyResolver`
  - `ParsePreviewRunner`
  - `IndexJobRunner` 基于 `ParseSnapshot` 的正式 materialization

### 5.1 `ParsePreviewRequested`

方向：

- `intake-pipeline -> indexing`

最少字段：

- `request_id`
- `source_file_id`
- `tenant_id`
- `collection_id`
- `source_binary_ref`
- `filename`
- `mime_type`
- `parser_profile_id`
- `trace_id`

说明：

- `parser_profile_id` 可以由上游调用方显式指定
- 如果未显式指定，则由 `ParsePolicyResolver` 按上游默认策略做保守决策
- resolver 的输出至少应固化：
  - `document_family`
  - `parser_profile_id`
  - `chunk_profile_id`
  - `parse_mode`
  - `strategy_source`
  - `upstream_default_strategy`
  - `decision_reason`

### 5.2 `ParseSnapshotReady`

方向：

- `indexing -> intake-pipeline / workbench-api`

最少字段：

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

### 5.3 `IndexBuildRequested`

方向：

- `publishing-worker -> indexing`

最少字段：

- `publish_id`
- `reindex_job_id`
- `final_doc_id`
- `tenant_id`
- `collection_id`
- `source_binary_ref`
- `parse_snapshot_id`
- `governance_overlay_ref`
- `target_index_version`
- `index_profile_id`
- `trace_id`
- `idempotency_key`

过渡期兼容字段可以存在：

- `canonical_asset_ref`
- `sanitized_asset_ref`
- `metadata_ref`

但它们只是发布侧辅助资产，不是正式解析或正式索引主输入。

### 5.4 `IndexReady`

方向：

- `indexing -> publishing-worker / retrieval`

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
- intake/workbench 的人工干预对象应是 `parser_profile_id`，不是上游内部 parser 名

## 7. 与 workbench-api 的关系

`workbench-api` 应只是 `indexing` 的受控观察与调试面。

它可暴露：

- ParseSnapshot 查询
- parser/chunker profile 调试
- chunk preview
- 手工复跑 preview

它不应暴露：

- 平台治理真相写入
- 文档生命周期推进
- 发布状态变更

## 8. 运行时实现约束

当前仓库已开始使用：

- `packages/ragflow_runtime`

后续实现约束应是：

- 低层 RAGFlow 能力尽量收敛到 `packages/ragflow_runtime`
- `services/indexing` 只依赖受控 runtime 和本地 contracts
- 临时 import alias 只是迁移辅助，不是长期结构

## 9. 可观测性

`services/indexing` 必须具备能支撑后续 parser/profile/chunk 优化的全链路埋点。

当前 indexing 主线至少记录三类对象：

- `RunTrace`
- `RunStep`
- `TraceArtifact`

当前服务内还提供轻量聚合指标出口：

- `/internal/metrics`

当前至少聚合：

- parse preview request/success counters
- parser profile 命中 counters
- parse mode 命中 counters
- strategy source counters
- upstream default strategy counters
- materialization request/success counters
- index profile 命中 counters
- preview / materialization duration summaries
- assembled chunk count summaries

### 9.1 Parse Preview Trace

`ParsePreviewRequested -> ParseSnapshot` 当前至少应记录：

- `parse_preview_requested`
- `parse_hint_detected`
- `parse_policy_resolved`
- `parse_snapshot_persisted`

当前至少应挂出的 artifact：

- runtime progress events
- parse snapshot

### 9.2 Index Materialization Trace

`IndexBuildRequested -> chunk materialization` 当前至少应记录：

- `index_build_requested`
- `index_build_job_created`
- `parse_snapshot_loaded`
- `token_chunks_assembled`
- `index_chunks_materialized`

当前至少应挂出的 artifact：

- normalized blocks
- chunk records

### 9.3 设计目标

这套埋点必须至少能回答：

- 某份文档为什么命中这个 `parser_profile_id`
- 本次 preview 用了什么 `parse_mode`
- 本次命中的是哪条上游默认策略
- 这次决策来自 manual override、collection default 还是 upstream default
- 生成了什么 `ParseSnapshot`
- 正式索引是否复用了同一份 snapshot
- 最终切成了多少 chunk
- 哪一步最慢、最不稳定、最容易退化

## 10. 一句话

`services/indexing` 的目标不是“消费一份 intake 产出的 markdown”，而是成为平台唯一正式的文档理解与索引构建服务，并用 `ParseSnapshot` 把预览、治理、正式索引收敛到同一条主链。
## 配置统一入口

`services/indexing` 的模型与后端配置统一收口在：

- [config.py](/E:/AI/My-Project/Enterprise%20KnowledgeBase/services/indexing/src/indexing_service/config.py)
- [services/indexing/.env.example](/E:/AI/My-Project/Enterprise%20KnowledgeBase/services/indexing/.env.example)

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

`backends.py` 与 `ragflow_runtime` 宿主兼容层都应从这个统一配置入口读取。

## 当前实施状态

截至 2026-05-25，`services/indexing` 已经完成的部分如下：

- preview 主链已经直接调用上游 `rag.app.*.chunk()`，不再以本地自造 parser/chunker 语义为核心
- `ParseSnapshot` 现在以 `parser_id / parser_config / upstream_chunks` 为核心输入输出
- request 级手动 `parser_id` 与 `parser_config` 覆盖已关闭，执行默认走上游 `file_service.get_parser` 风格
- formal materialization 已经可以从 `upstream_chunks` 生成 chunk records
- chunk records 已可以进一步生成 `IndexAssetBundle`
- 已具备 OpenSearch/Qdrant payload 生成链
- `services/indexing` 内部模型与索引后端配置已经统一收口到 `config.py`
- chat 与 embedding 已支持分开配置：
  - `chat` 可单独指向 DeepSeek
  - `embedding` 可单独指向硅基流动等 OpenAI-compatible embedding 服务

当前已经明确吸收进主链的上游 parser 语义包括：

- `presentation`
  - slide 级语义已进入正式 materialization
  - `section_path` 已保留 `Title -> Slide N`
  - citation anchor 已带 slide chunk 语义
- `table`
  - table metadata 聚合不再本地重写，已转为受控复用上游 `table_es_metadata`
  - `field_map` 与 `table_column_names` 已冻结进 snapshot
- `manual`
  - 优先承接上游 `section_paths`，不再本地重造章节路径
- `paper`
  - `authors`、`important_kwd` 等论文语义已进入 `vector_text` 与 metadata 组织
- `qa`
  - question 语义已进入 `section_path`、metadata 与 embedding 前文本组织

当前已经基本收口的上游写入语义包括：

- `insert_chunks()` 对应的通用 doc-store 字段骨架已经进入正式主链
- chunk / bundle / indexed_document 三层关联已经打通
- hidden parent chunk / hidden toc chunk 已可正式落库并受 `available_int` 控制
- 文档级 `IndexedDocument` 已可表达 parser、suffix、metadata、outline、可见/隐藏记录计数
- 上游通用兼容字段如 `kb_id / source_id / removed_kwd / pagerank_fea / chunk_data` 已进入主链或具备稳定映射策略

当前已经正式进入主链的治理入库语义包括：

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

这意味着当前 `indexing` 对治理的处理已经从：

- “顺手带几个治理字段入库”

变成了：

- “治理资产是正式索引物化输入的一部分”

当前已经开始进入持久化 registry 的生命周期真相包括：

- index build job
- active index registry
- indexed document
- parse snapshot
- chunk registry

这些对象现在已经不再只存在于 `InMemoryIndexingRepository` 的内存状态里，而是已可落到 shared persistence layer。

当前仍未完全收束的主要部分是：

- service runtime cache
- lifecycle 主线对持久化 registry 的使用还未覆盖所有 indexing 对象

所以当前状态应理解为：

- “版本与作业生命周期已经开始变硬”
- “解析快照与 chunk 总账也已经开始变硬”
- “持久化模式下数据库已经是 registry 真相来源”
- 但还没有到“所有 indexing 内部状态都只剩数据库一份真相”的结束态

当前已经定下但尚未完全吸收的上游语义包括：

- `naive`
  - 通用文本类 parser 的 embedding 输入组织细节还需要继续按上游真实行为补齐
- OCR / layout 相关 parser_config
  - 还需要继续承接上游对 `layout_recognize`、OCR、页面级参数的真实控制语义
- `task_executor.embedding()` 与 `insert_chunks()`
  - 通用主链核心字段已经基本吸收
  - 剩余主要是专用链字段与少量特殊后处理的最终取舍，而不是主干缺失

当前已经真正跑通、可用的后处理能力：

- `auto_keywords`
- `auto_questions`
- `auto_metadata`
- `content_tagging`
- `toc_extraction`

其中三类后处理当前的真实实现边界应理解为：

- `auto_metadata`
  - 已按上游 `task_executor -> gen_metadata -> update_metadata_to` 语义执行
  - metadata schema 合并优先走上游 `turn2jsonschema`
  - chunk 级 LLM 输出在文档级合并时，按上游 `update_metadata_to` 规则收敛，而不是本地自造 merge 逻辑
- `content_tagging`
  - 已优先按上游思路执行：先尝试复用检索器分布打标，再走 LLM tagging
  - 如果当前宿主没有完整 retriever/doc-store 支撑，则退化到内容命中补全，保证 preview/materialization 不被打挂
  - 因此它现在已经可用，但“完全等价于上游线上 tag 分布效果”仍依赖后续把真实检索器宿主接全
- `toc_extraction`
  - 已直接复用上游 `run_toc_from_text`
  - TOC 输出已保持上游 `level/title/chunk_id` 语义，并在正式 materialization 阶段映射为 hidden toc chunk 与 outline ids
  - 当前如果 LLM TOC 提取失败，仍保留受控宿主推断作为退化路径，目标是稳住主链而不是重新发明 TOC 体系

这三项当前的状态是：

- 已不再只是“止血”
- 已经进入正式 preview / snapshot / materialization 主链
- 但 `content_tagging` 的最佳效果仍然依赖真实 doc-store/retriever 宿主接全
- 因此“行为语义已基本对齐”，“线上效果完全等价”这件事还没有结束

当前整体状态可以概括为：

- 主干方向已经纠偏
- preview / snapshot / chunk materialization / bundle 输出已经立住
- embedding 执行权保留在 `indexing`，但 embedding 输入组织规则继续按上游 parser 语义吸收
- 通用主链的 doc-store 写入字段已经基本收口
- 文档级索引对象 `IndexedDocument` 已经立住
- 后处理增强链只完成了一部分
- 完整索引生命周期、深层专用 parser 语义吸收、更新/回滚/清理链路仍未完成

## 字段审计

截至 2026-05-25，`services/indexing` 对上游 `insert/write` 字段的处理原则已经明确：

- 不是为了“字段名一模一样”而机械照搬
- 真正需要保留的是字段背后的检索语义、结构语义、可见性语义和写入语义
- 当前实现优先吸收上游真实会影响效果和行为的字段
- 对只服务于专用链、图谱链或尚未接入子系统的字段，暂不盲目落库

### 已吸收的核心写入字段

当前已经正式进入 chunk record / OpenSearch / Qdrant payload 的字段包括：

- 文本与分词字段
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
- 标签字段
  - `tag_kwd`
  - `tag_feas`
- 结构与定位字段
  - `img_id`
  - `mom_id`
  - `position_int`
  - `page_num_int`
  - `top_int`
  - `row_id` 目前作为 citation/source block 辅助字段透传
- 可见性与写入控制字段
  - `available_int`
  - `kb_id`
  - `doc_id`
  - `final_doc_id`
  - `index_version_id`
  - `document_index_revision_id`
  - `indexed_document_id`
- 兼容与映射字段
  - `source_id`
  - `pagerank_fea`
  - `chunk_data`
  - `removed_kwd`
- 时间字段
  - `create_time`
  - `create_timestamp_flt`

这些字段已经不只是存在于内存对象，而是已经进入：

- `ChunkRecordRecord`
- `IndexAssetBundle`
- OpenSearch body
- Qdrant payload
- `IndexedDocument` 关联链

### 已吸收的文档级字段

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

### 暂未吸收但已识别的上游字段

以下字段目前没有作为通用企业知识库 indexing 主链的一部分正式落库：

- 当前这一组已经不再属于“未吸收”
- 它们已经进入正式 payload，但语义上仍按平台主键和平台生命周期来解释：
  - `kb_id`
  - `pagerank_fea`
  - `source_id`
  - `chunk_data`
  - `removed_kwd`

当前不优先吸收的原因分别是：

- `kb_id`
  - 现已作为兼容字段落库
  - 当前稳定映射到平台 `collection_id`
- `pagerank_fea`
  - 现已支持从 `source_metadata` 透传
  - 当前还没有形成完整的平台排序策略 owner
- `source_id`
  - 现已作为兼容字段落库
  - 当前稳定映射到 `source_file_id`
- `chunk_data`
  - 现已支持原样透传
  - 但当前只有上游 chunk 本身携带该结构时才会落库
- `removed_kwd`
  - 现已作为兼容字段落库
  - 当前平台删除/失活真相仍由 `available_int` 与版本生命周期控制

### 专用链字段暂不纳入通用 indexing 主链

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

这些字段不是“不重要”，而是：

- 它们属于上游专用 indexing 子系统
- 当前企业知识库主链还没有把 GraphRAG / RAPTOR 完整接进来
- 在未接入完整子系统前，不应把它们半截落库成“看起来像支持、实际上没有真正链路”的状态

一句话：

- 当前字段策略不是追求表面一致
- 而是优先保证上游真实行为字段已经进入正式索引主链
- 对专用链字段保持识别但不乱落库

如需继续推进，下一步优先级应为：

1. 对上游 `insert_chunks()` 与 doc-store schema 再做最后一轮逐项核对，确认通用主链无实质缺口
2. 明确 GraphRAG / RAPTOR / entity / table-structure 专用字段是否进入后续子系统，而不是混入通用主链
3. 继续做实 `auto_metadata`
4. 继续做实 `content_tagging`
5. 继续做实 `toc_extraction`
6. 然后再进入完整 index update / activate / rollback / cleanup

## 当前新增对齐点

截至 2026-05-26，这一轮又补齐了两类关键点：

- 后处理合并语义
  - `auto_metadata` 已不再使用本地自造 JSON merge 规则
  - 现在按上游 `update_metadata_to` 语义合并 chunk 级 metadata
- tagging 宿主语义
  - 当前会优先尝试复用上游风格的 retriever tagging
  - 宿主不具备该能力时，才退到受控内容命中补全
  - 这意味着 `indexing` 现在对 tagging 的态度是：
    - 行为优先对齐上游
    - 宿主缺口明确承认
    - 退化路径只负责保主链，不负责伪装成完整上游线上效果

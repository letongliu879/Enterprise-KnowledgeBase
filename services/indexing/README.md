# indexing

`services/indexing` 负责文档理解与索引构建。

详细设计见 [indexing.md](./indexing.md)。

## 核心链路

1. 预解析（Parse Preview）
2. ParseSnapshot 生成与持久化
3. 正式索引物化（Index Materialization）
4. Chunk Revision（发布后人工修订）
5. 索引版本生命周期（activate / rollback / cleanup）

## 技术基调

- Python + FastAPI
- 以 `packages/ragflow_runtime` 为受控运行时
- RAGFlow 多解析/分块子系统作为低层能力来源，不限于 DeepDoc
- 可吸收 ContextWeaver 的分块与上下文工程方法
- 写入 OpenSearch + Qdrant（hybrid backend）
- 维护 index version 与 indexed document 生命周期

## 职责边界

- `packages/ragflow_runtime` 只负责文档解析、分块和结构提取
- `services/indexing` 负责承接治理字段，并把解析结果写成正式索引记录
- 治理字段 owner 不是 `ragflow_runtime`

关于 embedding：

- `embedding` 请求由 `services/indexing` 执行
- 但 `embedding` 之前的文本组织语义，应继续对齐上游 RAGFlow 各 parser 的真实行为
- 这样既保留上游效果，也保留后续人工或 agent 修 chunk 后重算 embedding 的控制权

## 约束

- `services/indexing` 不只是不能自建本地 parser profile/策略层，而是整条解析链都不得发明本地替代实现
- parser 选择、parser_config 语义、解析编排、chunk 语义、结构抽取语义，原则上都应直接承接上游 RAGFlow 真实链路
- 本地层只允许做宿主适配、运行时隔离、快照冻结、索引物化与可观测性承接，不允许把上游解析链"翻译"成另一套平台自定义语义

## 服务面

### 对外端点（Inbound）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/internal/parse-previews` | 提交预解析请求（异步，202 Accepted） |
| `GET` | `/internal/parse-snapshots/{parse_snapshot_id}` | 查询 ParseSnapshot |
| `GET` | `/internal/parse-snapshots/{parse_snapshot_id}/chunks` | 分页查询 snapshot 内的 upstream chunks |
| `POST` | `/internal/index-jobs` | 提交正式索引构建请求（异步，202 Accepted） |
| `GET` | `/internal/index-jobs/{job_id}` | 查询索引构建任务状态 |
| `GET` | `/internal/indexed-documents` | 列出已索引文档（支持按 collection_id / index_version / final_doc_id 过滤） |
| `POST` | `/internal/index-versions/{index_version_id}/activate` | 激活索引版本 |
| `POST` | `/internal/index-versions/{index_version_id}/rollback` | 回滚索引版本到上一个 active 版本 |
| `POST` | `/internal/index-versions/{index_version_id}/cleanup` | 清理废弃索引版本 |
| `GET` | `/internal/index-versions/{index_version_id}` | 查询索引版本元数据 |
| `POST` | `/internal/parser-profiles/validate` | ParserProfile 运行时校验与 canonicalize |
| `POST` | `/internal/chunks/{evidence_id}/revisions` | 创建 chunk revision（幂等，idempotency_key 去重） |
| `GET` | `/internal/chunk-revisions/{revision_id}` | 查询 chunk revision 状态 |
| `POST` | `/internal/chunk-revisions/{revision_id}/materialize` | 执行 chunk revision 物化 |
| `GET` | `/internal/chunks` | 按租户/主体查询 active chunks（含 ACL 过滤） |
| `GET` | `/internal/metrics` | 服务内部聚合指标快照 |

### 外部调用（Outbound）

| 方向 | 方法 | 路径 | 说明 |
|------|------|------|------|
| indexing -> retrieval | `POST` | `/internal/index-projections/sync` | 索引激活后同步 index version、chunks、published document 投影 |
| indexing -> retrieval | `POST` | `/internal/cache/purge` | 激活或 revision 物化后清理检索缓存 |

### 关键端点详情

#### `POST /internal/parser-profiles/validate`

- **输入**：`parser_profile_id`, `parser_id`, `parser_config`, `chunk_profile_id` (optional), `tenant_id`, `collection_id` (optional), `version` (optional)
- **校验**：parser_id 支持范围、chunk_token_num 范围、config 类型
- **输出**：`valid`, `canonical_config`, `profile_hash`, `warnings`, `errors`, `runtime_owner` (= "indexing"), `validator_version`
- **副作用**：不写 admin 表、不创建 ParseSnapshot、不触发索引 job

#### `POST /internal/parse-previews`

- 输入：`ParsePreviewRequestedCommand`
- 输出：`ParsePreviewAccepted`（含 `parse_snapshot_id`）

#### `POST /internal/index-jobs`

- 输入：`IndexBuildRequestedCommand`
- 输出：`{build_job_id, status, accepted_command}`
- 行为：根据 `request_type` 决定构建后是否自动激活
  - `publish` / `reindex`：构建 + 激活原子操作
  - `lifecycle_tombstone`：仅构建，不激活

#### `POST /internal/chunks/{evidence_id}/revisions`

- 幂等创建 revision（`idempotency_key` 去重）
- 验证 base chunk 存在且 tenant/collection 匹配
- 404：base chunk 不存在
- 409：tenant/collection 不匹配
- 200：返回已有 revision（重复 idempotency_key）

#### `POST /internal/chunk-revisions/{revision_id}/materialize`

- 加载 revision 和 base chunk
- 应用 operation（`update` / `delete` / `hide`）
- 生成新 `ChunkRecord`，重新计算 `chunk_hash`
- 调用 `build_index_asset_bundle` + `HybridIndexBackend.write_bundle`
- 旧 chunk `available_int=0`，新 chunk `available_int=1`
- 更新 revision status -> `active`
- materialization 失败时 revision status -> `failed`，旧 chunk 不下线

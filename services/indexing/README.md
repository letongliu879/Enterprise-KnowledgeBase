# indexing

`services/indexing` 负责文档理解与索引构建。

详细设计见 [indexing.md](./indexing.md)。

## 核心链路

1. 预解析
2. ParseSnapshot
3. 分块
4. embedding
5. 索引写入

## 技术基调

- Python + FastAPI/worker
- 以 `packages/ragflow_runtime` 为受控运行时
- RAGFlow 多解析/分块子系统作为低层能力来源，不限于 DeepDoc
- 可吸收 ContextWeaver 的分块与上下文工程方法
- 写入 OpenSearch + Qdrant
- 维护 index version

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

对外：

- `GET /health`
- `POST /internal/parser-profiles/validate` — ParserProfile 运行时校验与 canonicalize
  - 输入：`parser_profile_id`, `parser_id`, `parser_config`, `chunk_profile_id` (optional), `tenant_id`, `collection_id` (optional), `version` (optional)
  - 校验：parser_id 支持范围、chunk_token_num 范围、config 类型
  - 输出：`valid`, `canonical_config`, `profile_hash`, `warnings`, `errors`, `runtime_owner` (= "indexing"), `validator_version`
  - 无副作用：不写 admin 表、不创建 ParseSnapshot、不触发索引 job
- `POST /internal/parse-previews` — Parse preview（已有）
- `GET /internal/parse-snapshots/{id}` — 查询 ParseSnapshot（已有）
- `POST /internal/index-versions/{id}/activate` — 激活索引版本（已有）
- `POST /internal/index-versions/{id}/cleanup` — 清理索引版本（已有）

外部调用（indexing → retrieval）：

- `POST /internal/index-projections/sync` — 向 retrieval 同步 index version、index registry、published document、chunk 投影

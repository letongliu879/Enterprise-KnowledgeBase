# Indexing
Current repository status: `src/` is still under active construction, but lifecycle truth is no longer only in memory.

Current status update:

- parse preview / snapshot 主链仍以本地 service 代码驱动
- chunk materialization / bundle 写出主链已经可用
- governance assets 已正式进入 materialization 主线
- index build job / active index registry / indexed document 状态现在已可落到 shared persistence layer
- parse snapshot registry 现在也已可落到 shared persistence layer
- chunk registry 本体现在也已可落到 shared persistence layer
- 在持久化模式下，version/document/snapshot/chunk registry 不再依赖 JSONL projection 作为真相来源

仍未完成的部分主要是：

- 当前仍保留少量 service runtime cache 作为进程内加速层
- 但持久化模式下，数据库已经是 lifecycle 真相来源

负责解析与索引全链路的核心运行时：

1. 预解析
2. ParseSnapshot
3. 分块
4. embedding
5. 索引写入

技术基调：

- Python + FastAPI/worker
- 以 `packages/ragflow_runtime` 为受控运行时
- RAGFlow 多解析/分块子系统作为低层能力来源，不限于 DeepDoc
- 可吸收 ContextWeaver 的分块与上下文工程方法
- 写入 OpenSearch + Qdrant
- 维护 index version

本模块不负责文档准入、权限审批、最终发布可见性和在线检索组装。

职责边界再强调一次：

- `packages/ragflow_runtime` 只负责文档解析、分块和结构提取
- `services/indexing` 负责承接治理字段，并把解析结果写成正式索引记录
- 治理字段 owner 不是 `ragflow_runtime`

关于 embedding，再补一条硬边界：

- `embedding` 请求由 `services/indexing` 执行
- 但 `embedding` 之前的文本组织语义，应继续对齐上游 `RAGFlow` 各 parser 的真实行为
- 这样既保留上游效果，也保留后续人工或 agent 修 chunk 后重算 embedding 的控制权

详细设计见 [indexing.md](./indexing.md)。

当前仓库已经开始接入受控的 `packages/ragflow_runtime`，并以 `ParseSnapshot` 作为 intake/workbench 与正式索引之间的核心接缝。

补充约束：

- `services/indexing` 不只是不能自建本地 parser profile/策略层，而是整条解析链都不得发明本地替代实现。
- parser 选择、parser_config 语义、解析编排、chunk 语义、结构抽取语义，原则上都应直接承接上游 `RAGFlow` 真实链路。
- 本地层只允许做宿主适配、运行时隔离、快照冻结、索引物化与可观测性承接，不允许把上游解析链“翻译”成另一套平台自定义语义。

当前已经落地的 indexing 控制面与链路骨架包括：

- `DocumentFamily`
- `ParserProfile`
- `ParsePolicyResolver`
- `ParsePreviewRequested -> ParseSnapshot`
- `IndexBuildRequested -> ParseSnapshot materialization`
- `RunTrace / RunStep / TraceArtifact` 级别的 indexing 埋点

约束：

- `services/indexing` 只通过受控 runtime 使用 RAGFlow 低层能力。
- 不直接依赖 `upstream/ragflow` 的产品宿主层。
- 不再保留独立 `services/ragflow-adapter` 作为最终服务形态。

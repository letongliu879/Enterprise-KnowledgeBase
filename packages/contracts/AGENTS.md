# contracts — 共享契约与数据模型

## 定位
contracts 是 Reality-RAG V2 唯一正式的跨服务类型库，所有微服务**必须**从这里导入共享类型，不得自行定义重复的数据结构。

**不做的事**：不持有业务逻辑、不执行 I/O、不依赖任何服务层代码（仅依赖 `pydantic>=2.0`）。

## 边界原则
- 所有跨服务 wire format 的 model 定义在 `models.py`（~110 个 model）
- 枚举集中在 `enums.py`（30+ StrEnum），wire value 统一使用 `lower_snake_case`
- `IndexBuildRequestedCommand` 是 indexing-service 的 canonical wire command，wire 字段用 `doc_id`（非 `final_doc_id`），DB 内部用 `final_doc_id`
- 状态机集中在 `state_machine.py`，任何服务不得绕过状态机直接赋值状态
- 配置文件加载逻辑在 `config.py`，环境变量链式 fallback
- 索引后端命名规范在 `index_naming.py`，所有服务统一使用

## 核心数据流
```
models.py (pydantic models)  ←── 所有服务从这里导入
  ├── enums.py               ←── wire value = lower_snake_case
  ├── state_machine.py       ←── 状态转换唯一入口
  ├── indexing_models.py     ←── chunk / snapshot / index version 记录
  ├── config.py              ←── env → dataclass 配置加载
  └── index_naming.py        ←── OpenSearch/Qdrant 索引名生成
```

## 关键对象
- `IndexBuildRequestedCommand`：indexing 的 canonical wire command（`models.py:1174`）
- `KnowledgeContext`：检索产出的主要产物（evidence + assembled context）
- `CacheKeyComponents`：检索缓存 key 的所有维度（`models.py:652`）
- `ChunkRecord`：写入后端的完整 chunk 记录（`indexing_models.py:40`）
- `CanonicalMetadata`：企业治理记录（`models.py:157`）
- `OutboxEvent`：事务性 outbox 事件记录（`models.py:842`）
- `CommandEnvelope`：管理控制命令的稳定信封（`models.py:1466`）

## 约束
- 任何服务**不得**发明自己的跨服务数据结构，wire format 必须用这里定义的 model
- `final_doc_id` 是内部 DB 字段名，wire 协议必须使用 `doc_id`（`test_wire_drift_guard.py` 会检测漂移）
- 状态转换必须经过 `state_machine.py` 中的状态机，禁止 `InvalidTransitionError`
- 所有跨服务事件类型必须先在 `EventType` 枚举中注册
- model 字段命名统一 `snake_case`，PascalCase 仅用于类名
- 配置文件加载用 `config.py` 的 `load_indexing_config()`，环境变量前缀 `INDEXING_*`

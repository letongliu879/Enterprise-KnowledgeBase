# persistence — 共享持久化层

## 定位
persistence 是 Reality-RAG V2 唯一正式的数据访问层。所有 PostgreSQL 操作用于此包。任何服务**不得**定义自己的 ORM 模型或复制 repository 逻辑。

**不做的事**：不包含业务逻辑（repository 只做数据转换，不做决策）、不管理事务边界（由调用者控制）、不属于应用层服务。

## 边界原则
- **Repository 模式**：每个表一个 Repository，构造函数接收 `Session`，返回 contracts 定义的 Pydantic model
- **Outbox 模式**：业务状态和事件在同一 DB 事务中写入，`OutboxDispatcher` 异步轮询投递
- **Telemetry 是 best-effort**：写入失败只 log warning，不抛异常
- **SQLAlchemy Session** 由调用方传入（service 层管理），persistence 不创建也不关闭
- **Lazy Engine**：`get_session()` 首次调用才创建 engine，允许 import 时无数据库连接
- **Owner 注解**：每个 ORM model 有 `Owner: <service>` 注释，标明职责归属
- **JSON 列是过渡方案**：长期目标是把 JSON 移出 PostgreSQL 到对象存储

## 核心数据流
```
Service Layer
  │
  ▼ Repository (one per table)
  ├── 接收 SQLAlchemy Session
  ├── ORM Model ←→ Contract Pydantic Model 转换
  └── 返回 contracts 定义的 type
  │
  ▼ EventPublisher (同一 Session 事务)
  ├── 写入 OutboxEventModel
  └── OutboxDispatcher 异步投递
  │
  ▼ IngestionMonitorStore (文件系统 fallback)
  └── JSON + JSONL 文件监控（低关键性路径）
```

## 关键对象
- `EventPublisher`：事务性 outbox 事件发布器（`outbox.py:25`）
- `OutboxDispatcher`：后台轮询投递器（`outbox.py:191`）
- `IngestionMonitorStore`：文件系统摄入监控（`ingestion_monitor.py:19`）
- `IntakeMetrics`：Prometheus 指标定义（`metrics.py:35`）
- `TelemetryStore`：best-effort 遥测持久化（`telemetry.py:95`）
- `PersistentRunAuditStore`：RunTrace/Step/Artifact 持久化外观（`run_audit_store.py:12`）

## ORM Model 约定
- 命名：`{EntityName}Model`（`models.py` 中 50+ model）
- Table 名：`snake_case` 复数（`admin_users`, `outbox_events`, `llm_call_log`）
- 索引名：`ix_` 前缀
- 唯一约束：`uix_` 前缀
- 所有 model 有 `Owner` 注释
- 乐观锁：`IntakeJobModel` 有 `state_version` 字段

## 约束
- 禁止直接在 Service 层使用 ORM Model —— 必须通过 Repository 获取 contracts 的 Pydantic model
- 禁止绕过 Repository 直接操作 Session
- `final_doc_id` 是 DB 内部字段名，wire 协议必须用 `doc_id`
- 事务边界由调用者（Service）管理，Repository 不提交也不回滚
- 跨服务投影同步（API Key / Index / Retrieval Profile）走 `*ProjectionSync` command
- `ChunkRegistryRepository` 是可选的（`try/except ImportError`），其他服务不应依赖
- SQLite 兼容性仅用于测试（`override_url_for_testing`）
- 不要在生产环境中使用 `create_all()` / `drop_all()`

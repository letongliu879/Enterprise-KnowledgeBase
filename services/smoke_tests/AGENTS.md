# smoke_tests — 跨服务端到端烟雾测试

## 定位
smoke_tests 是整个平台的**最终防线**，验证所有 Python 服务在真实 HTTP 边界上的集成正确性。它不是单元测试，不是契约测试——它测试的是服务之间的**通信、状态流转、数据一致性**。

**不做的事**：取代服务的单元测试、integration test、性能测试、UI 测试。不 mock 内部逻辑——用 fake 替代外部依赖（LLM/vector DB），但服务间 HTTP 走的是真实路由。

## 两种运行模式

### 1. In-process ASGI 模式（conftest.py + test_intake_real_chain.py）
所有 Python FastAPI 服务挂载到一个 combined_app，httpx 自动注入 ASGITransport。跨服务 HTTP 调用**不进网络**，全部在进程中路由。

核心机制：conftest.py 在 session fixture 中 patcht httpx.AsyncClient.__init__ + httpx 顶层函数（get/post/put/patch/delete），使其在未指定 transport 时默认使用 ASGITransport(combined_app)。

适用场景：本地开发、CI 快速验证。不需要任何外部基础设施（SQLite 替代 PostgreSQL）。

### 2. Deployment 模式（test_deployment_smoke.py）
每个服务作为独立 OS 子进程启动，通过 real localhost HTTP 通信。使用 curl 而不是 httpx 客户端，避免 patching 污染。

适用场景：部署验证、预发布环境。需要真实 PostgreSQL、OpenSearch、Qdrant。

## 边界原则
- conftest.py 的 `_apply_smoke_patches` fixture 用 `scope="session"`，在**所有测试之前**就 patcht httpx。任何需要测试 patching 行为的用例必须先理解这个生命周期
- 所有 fixture 均为 `scope="module"`：服务维护进程内状态（intake 的 `_documents`、indexing repository caches），function-scoped 会丢失状态
- DB 在每个 module 开始前通过 `_reset_smoke_db` 销毁重建（`drop_all()` + `create_all()`）
- `_FakeSmokeReviewer` 永远 approve（confidence=0.99），不验证 LLM reviewer 逻辑——那由 intake-runtime 的单元测试覆盖
- `RAGFlowConverter._parse_via_indexing` 被替换为 fake，写入 fake ParseSnapshotRecord 到 SQLite——不要求 RAGFlow 真实运行
- 外部依赖（LLM / embedding / OpenSearch / Qdrant / Redis）在 in-process 模式下全部禁用——环境变量被 pop 掉，索引后端默认 noop
- Deployment 模式使用 `curl` 而不是 httpx 客户端——这是为了避免 httpx patching 对子进程 HTTP 调用的干扰

## 核心数据流（split-owner path）
```
workbench upload -> document-service -> FileReady event -> orchestrator
  -> conversion stage（RAGFlowConverter + fake parse -> agent review）
  -> review stage（FakeSmokeReviewer auto-approve）
  -> approval-service（approve-and-publish）
  -> publishing stage（persist document + policy）
  -> indexing（build index）
  -> workbench task reconciliation（ProjectionReconciler）
```

执行引擎：`drain_real_chain_for_source_files()` 驱动四个 OutboxDispatcher（orchestrator / conversion / review / publishing）轮流 poll，直到 source file 到达 terminal state。

## 关键对象 / 概念
- **combined_app**：conftest.py 中创建的 FastAPI 实例，所有服务 app mount 其上。mount 顺序有讲究：workbench 使用 `_PrefixApp` 重新添加 mount strip 掉的前缀；admin 直接 mount 在 `/`（因为它的路由自带 `/admin`）
- **`_AsyncClientWrapper`**：同步外观模式的 async HTTP 客户端。处理嵌套事件循环——当在已有 running loop 中被调用时，将 coroutine 卸载到新线程的新事件循环中执行
- **`_SyncHttpxModuleProxy`**：代理对象替换 ingestion_worker 中的 `httpx` 模块引用，避免全局 `httpx.Client` 突变
- **`_PrefixApp`**：ASGI 中间件，在 scope["path"] 前重新添加 mount 时被 strip 掉的路径前缀
- **`drain_real_chain_for_source_files()`**：核心调度函数，接受 source_file_ids 列表，驱动 intake 全链路最多 40 轮（max_rounds=40）
- **`reconcile_workbench_tasks()`**：运行 ProjectionReconciler，将 intake 的状态投影同步到 workbench 的 task 表

## 约束
- deployment 模式跳过测试的条件：infrastructure 不可用（PostgreSQL/OpenSearch/Qdrant/Redis 端口无响应）
- `drain_real_chain_for_source_files` 必须在 `_reset_smoke_db` fixture 之后调用（依赖 DB schema 已创建）
- 修改 conftest.py 中的 `combined_app` mount 配置时，必须同步更新 test_deployment_smoke.py 中的 `CORE_SERVICES` 和环境变量
- 新增服务需要在 conftest.py 中 import app -> mount + test_deployment_smoke.py 添加 service config + _set_service_env 中添加对应的环境变量
- deployment 模式的 service cmd 依赖当前 host 的 Python 环境和系统安装的 uvicorn 和 curl
- conftest.py 中 `os.environ` 的修改在 session fixture 生命周期内**全局生效**，可能影响其他测试套件——所以仅在 smoke_tests 目录下运行这些测试

## 已知的集成缺陷（已在 smoke 中被发现并修复）
参见 README.md "Integration Gaps Discovered & Fixed" 章节。这些是 smoke_tests 最核心的**价值证明**——它们证明了为什么需要这套测试。

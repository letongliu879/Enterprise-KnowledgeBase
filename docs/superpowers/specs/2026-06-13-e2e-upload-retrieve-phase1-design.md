# Phase-1 E2E：文档上传 → 解析 → 检索

## 1. 目标

建立一条可重复运行的端到端回归用例，覆盖用户通过 web 完成“文档上传 → 后台解析/索引 → 检索结果展示”的完整链路，并包含关键负向与边界场景。

## 2. 方案选型

采用 **Playwright 自动化 + agent-browser 智能断言** 的混合方案：

- **Playwright**：负责稳定的浏览器操作（打开页面、登录、文件上传、点击菜单、等待 URL/元素、截全屏）。
- **agent-browser**：负责“阅读”检索结果页面，进行语义级断言（例如“页面显示了检索到的证据片段”）、检查 console 无错误、识别 Issues badge。
- **pytest** 作为测试 runner。

选择理由：Playwright 解决文件上传与稳定交互问题，agent-browser 保留对复杂页面状态的语义判断能力，避免为每个新 UI 写死选择器。

## 3. 范围

### 3.1 主路径

1. 打开 `/documents`。
2. 上传 `fixtures/sample.pdf`。
3. 通过 admin / indexing API 轮询，直到文档状态为 `indexed`（超时 60 秒）。
4. 打开检索页面，选择当前 collection，输入与文档内容相关的查询。
5. agent-browser 断言：页面展示证据片段、无 Issues badge、console 无 error。

### 3.2 负向与边界场景

| 用例 | 触发 | 期望 |
|---|---|---|
| 上传非 PDF 文件 | 选择 `.txt` / `.exe` | 前端提示文件类型不支持，不上传 |
| 空查询 | 检索页不输入内容直接提交 | 前端校验阻止或提示输入查询 |
| 未索引文档检索 | 上传后立即检索，跳过轮询 | 检索结果为空或提示“暂无索引数据” |
| 服务未就绪 | 启动前 health check 失败 | 用例 skip 并给出清晰错误 |
| 索引超时 | 文档未在阈值内变为 `indexed` | 用例 fail 并附带轮询日志与截图 |

## 4. 测试数据隔离

- 每个用例启动时在 admin API 创建唯一 `collection-e2e-<uuid>`。
- 在该集合下上传唯一命名的测试文档。
- 用例结束时（包括失败路径）调用 admin API 删除 collection 及其投影数据。
- 失败时保留截图与 Playwright trace，便于排查。

## 5. 关键组件

| 组件 | 职责 |
|---|---|
| `tests/e2e/conftest.py` | Playwright fixture、服务健康检查、唯一 collection fixture |
| `tests/e2e/phase1_upload_retrieve.py` | 主路径与负向用例 |
| `tests/e2e/helpers/services.py` | admin / indexing API 轮询、创建/删除 collection |
| `tests/e2e/helpers/agent_assert.py` | agent-browser 语义断言封装 |
| `tests/e2e/fixtures/sample.pdf` | 小型正向测试文档 |
| `tests/e2e/fixtures/invalid.txt` | 负向用例非法文件 |

## 6. 数据流

```
pytest
  ├─ conftest: 健康检查 + 创建唯一 collection
  ├─ Playwright: 打开 /documents → 上传 sample.pdf
  ├─ helpers.services: 轮询文档状态直到 indexed
  ├─ Playwright: 打开 /search，选择 collection，输入查询
  ├─ helpers.agent_assert: agent-browser 验证结果可见、无错误
  └─ conftest teardown: 删除 collection，失败时保留截图/trace
```

## 7. 错误处理与失败分类

失败时自动归类，便于快速定位根因：

- `FRONTEND_ERROR`：页面出现 Issues badge 或 console error。
- `INDEXING_TIMEOUT`：文档未在阈值内变为 `indexed`。
- `RETRIEVAL_EMPTY`：索引完成但检索无结果。
- `SERVICE_UNAVAILABLE`：依赖服务未启动或健康检查失败。
- `UPLOAD_REJECTED`：文件上传被前端或服务拒绝。

## 8. 成功标准

- 主路径与至少 3 个负向用例在本地稳定通过。
- 重跑不依赖旧数据，测试数据自动清理。
- 失败截图能直接定位到上述五类根因之一。

## 9. 依赖与前提

- 本地基础设施已启动：PostgreSQL、OpenSearch、Qdrant、Valkey。
- Python 服务已启动：admin、indexing、workbench-api、intake-pipeline（含 document-service / ingestion）。
- Java 服务已启动：access、retrieval（或 smoke 对应端口）。
- 已配置 `ACCESS_INTERNAL_API_KEY` 并同步到 access runtime。

## 10. 后续阶段

本设计仅覆盖第一阶段“上传 → 检索”。后续可依次加入：

- 第二阶段：审批工作流（上传 → 提交 → 审批 → 发布）。
- 第三阶段：管理配置生命周期（collection / retrieval profile / api-key）。

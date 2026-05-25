# Enterprise KnowledgeBase 项目总览

## 1. 这不是在“恢复 Reality-RAG”

`Enterprise KnowledgeBase` 不是把旧项目 `Reality-RAG` 原样救回来，也不是把 `RAGFlow` 和 `ContextWeaver` 整套产品搬进来。

它的正确定位是：

- 保留 `Reality-RAG` 已经想清楚的服务边界
- 直接复用 `RAGFlow` 在解析、分块、工作台上的成熟运行时能力
- 吸收 `ContextWeaver` 在上下文工程上的方法
- 把治理真相、生命周期真相、权限真相留在本平台

一句话说，当前项目应该把旧项目当作经验来源，把 `upstream/ragflow` 当作受控引擎，而不是把任何一个上游项目当成平台本体。

## 2. 当前项目的三层真相

### 2.1 平台治理真相

这一层由本仓库自己的平台服务负责，核心标识应围绕：

- `tenant_id`
- `collection_id`
- `final_doc_id`
- `published_documents`

它负责回答：

- 这份文档属于哪个 collection
- 谁能看
- 当前是否已发布
- 当前生命周期状态是什么
- 检索时是否允许被返回

这一层不能让给 `RAGFlow` 的 `dataset_id`、`file_id`、`document_id`。

### 2.2 解析与分块运行时真相

这一层主要由 `upstream/ragflow` 提供，负责：

- 文档解析
- OCR / layout 恢复
- ParseSnapshot
- chunk 生成
- chunk 预览
- dataflow / pipeline 工作流解析
- 解析工作台交互

这层真相是“如何把文档理解并切开”，不是“平台最终承认哪份文档、谁能访问它”。

### 2.3 在线检索执行真相

这一层主要由 `services/retrieval` 负责，围绕：

- `CollectionRetrievalPlan`
- active index
- retrieval profile
- `KnowledgeContext`

它负责回答：

- 这次查询应该在哪些 collection 上执行
- 每个 collection 当前绑定哪套索引
- 该走哪些召回、融合、精排、扩展、打包策略

这一层不能反向篡改平台治理真相。

## 3. 当前仓库里什么已经成形了

### 3.1 已经比较清晰的主线

- `contracts/`
  - 当前应继续作为跨服务契约唯一来源
- `packages/contracts`
  - Python 侧运行时契约包
- `packages/persistence`
  - 持久化模型和仓储承载位
- `packages/documents`
  - 共享文档域承载位
- `services/intake-pipeline`
  - 这是当前最完整的治理主线文档区域
- `services/indexing`
  - 解析 owner 应收敛到这里，而不是继续留在 intake 的轻量转换链里
- `services/retrieval`
  - 这不是纯设计稿，已经有 Java 服务代码、配置和测试
- `upstream/ragflow`
  - 当前项目真正依赖的解析/分块/workbench 运行时分叉

### 3.2 还不够稳定或还没真正落地的部分

- `services/workbench-api`
  - 当前目录能看到虚拟环境和 `__pycache__`，但缺少可维护的源码主线
  - 这更像本地实验或过渡运行形态，不宜当成稳定边界依据
- `services/access`
  - 目标架构里应存在，但当前仓库尚未形成可读主线
- `services/admin`
  - 目标架构里应存在，但当前仓库尚未形成可读主线
- `services/indexing`
  - 目标职责已经很明确，但当前仓库里更多还是由 `upstream/ragflow` 承载其运行时能力

## 4. 当前最可信的架构判断

结合仓库现状，当前项目更接近下面这个实际结构，而不是旧项目文档里的“完整最终态”：

```text
Enterprise KnowledgeBase
  -> intake-pipeline 负责治理边界与发布真相
  -> indexing 负责预解析、ParseSnapshot、正式索引构建
  -> upstream/ragflow 负责 indexing 内部运行时
  -> retrieval 负责 Java 在线检索主链
  -> contracts/packages 负责跨服务契约和共享基础
  -> workbench-api 是未来工作台受控接缝
```

这意味着近期主线不该是“再造一个大而全的平台骨架”，而应该是：

1. 先把治理边界和 RAGFlow 运行时边界钉死。
2. 再把 intake 发布事实和 retrieval 消费事实接通。
3. 最后再补 access、admin、稳定版 workbench seam。

## 5. 如何正确使用旧项目文档

`Reality-RAG` 的旧文档现在最有价值的，不是目录结构，而是边界判断。

可以继续使用的内容：

- 平台自己拥有治理真相
- Java 做在线 retrieval 主链
- Python 做摄入、审批、发布、索引构建
- `contracts/` 是跨语言契约中心
- trace / audit / replay 是一等能力

不能继续照搬的内容：

- “上游能力移植”作为项目主叙事
- 为了迁移而迁移的大量 adapter/镜像层
- 把上游成熟模块先拆碎再本地重写
- 让 `RAGFlow` 的对象模型反客为主

## 6. 对当前项目最重要的三条纪律

### 6.1 不让 workbench 对象升格为平台真相

`dataset`、`file`、`chunk` 可以存在，但只能服务于解析工作台和运行时，不得替代：

- collection 治理
- 文档生命周期
- ACL
- 发布状态

### 6.2 不让 retrieval 直接依赖上游产品宿主

`services/retrieval` 可以吸收 `RAGFlow` 和 `ContextWeaver` 的策略、参数、行为语义，但不能把它们的产品边界和宿主模型搬进 Java 主链。

### 6.3 不把过渡层误认成最终架构

当前仓库里有些目录存在，但并不代表它们已经是稳定主线，例如：

- `services/workbench-api`

今后写文档、做拆分、删目录时，都应优先看“谁在承载真实运行时”和“谁拥有最终真相”，而不是只看目录名。

## 7. 推荐的近期建设顺序

1. 固化 `upstream/ragflow` 的运行时白名单和裁剪边界。
2. 新增 `ParseSnapshot` 主线，明确预解析与正式索引的统一输入。
3. 明确 intake 发布事实如何投影给 retrieval。
4. 把 `services/retrieval` 作为当前最先形成闭环的在线主链继续做实。
5. 为 workbench 补一个真正可维护的受控 API 层，而不是继续依赖临时运行产物。
6. 最后再补统一的 `access` 与 `admin` 外壳。

## 8. 一句话

`Enterprise KnowledgeBase` 的正确方向不是“把旧项目补完”，而是“用旧项目的边界经验，围住 `RAGFlow` 和 `ContextWeaver` 的高价值能力，收敛成当前仓库自己的平台主线”。

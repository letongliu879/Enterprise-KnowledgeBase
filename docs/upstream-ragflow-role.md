# upstream/ragflow 在当前项目里的角色

## 1. 基本定位

`upstream/ragflow` 在当前项目里应当被定义为：

- 解析引擎
- 分块引擎
- intake workbench 运行时
- dataflow / pipeline 解析运行时

它不应被定义为：

- 平台治理系统
- 文档生命周期真相源
- 权限真相源
- 在线检索主链宿主

## 2. 为什么当前项目需要它

当前项目真正需要 `RAGFlow` 的地方，主要不是“知识库产品外壳”，而是这些成熟能力：

- PDF / Office / 富文本解析
- OCR 与 layout-aware 文档理解
- chunk 生成与 chunk 预览
- parser / chunker 参数调试
- pipeline / dataflow 解析流
- 文档工作台交互

这些能力自己重写，成本高、细节多、风险大。

## 3. 什么可以直接借

### 3.1 运行时能力

- `deepdoc` 相关解析能力
- 结构恢复和版面理解
- chunking 相关能力
- dataflow / pipeline 相关执行能力

### 3.2 工作台交互

- 文件列表
- 解析状态
- chunk 预览
- 参数调试
- 解析重跑

但这些 UI/交互只能服务于“工作台”，不能变成平台治理对象模型。

## 4. 什么不能让它拥有

- collection 治理真相
- `final_doc_id`
- 发布状态
- ACL / principal 权限语义
- 在线检索权限模型
- 平台生命周期语义

简单说：

- `RAGFlow` 可以告诉我们“这份文件被切成了哪些 chunk”
- 但不能替平台决定“这份文档是否已发布、谁可以检索它”

## 5. 为什么 `agent` 现在不能直接删

当前 `upstream/ragflow` 里，`agent` 虽然不是普通 dataset/chunk 流程的绝对中心，但它仍然与这些路径有关：

- `pipeline/dataflow`
- canvas / graph 定义
- 部分启动期导入

如果你确认当前项目还要保留 `pipeline/dataflow` 这种解析模式，那么 `agent` 现在就不是“无关目录”，而是“应该先解耦再考虑删除”的目录。

## 6. 当前项目对 `RAGFlow` 的正确态度

### 6.1 把它当受控引擎

正确做法是：

- 明确运行时白名单
- 只加载 intake/workbench 需要的入口
- 保留 dataflow 所需依赖
- 把 chat / memory / mcp / plugin / agent product 边界逐步隔离出去

### 6.2 不把它当平台骨架

错误做法是：

- 让 `dataset/file` 升格成平台主对象
- 让 `RAGFlow` 的 REST 边界主导平台边界
- 让检索、审批、生命周期都围着它转

## 7. 物理裁剪时的判断原则

### 7.1 一般可删的

这类目录通常不属于服务运行必需：

- `.agents`
- `.github`
- `docs`
- `helm`
- `example`
- `.pytest_cache`
- `logs`
- `__pycache__`
- `web/dist`
- `web/src/stories`
- `web/.storybook`

它们大多属于：

- 协作元数据
- CI 配置
- 文档
- 示例
- 缓存
- 构建产物
- 演示代码

### 7.2 当前不建议直接删的

- `agent`
  - 因为仍与 dataflow / pipeline 有直接关系
- `sdk`
  - 不是运行时必需，但对后续外部集成、接口对齐、调用方式参考仍有价值
- `memory`
  - 当前虽属待裁剪域，但仍可能残留导入关系
- `mcp`
  - 同样属于待裁剪域，删除前应先确认导入链彻底切断

## 8. 当前项目最终应该收敛成什么关系

比较理想的关系是：

```text
Enterprise KnowledgeBase platform
  -> owns governance, lifecycle, retrieval boundary

upstream/ragflow
  -> provides parse/chunk/workbench/dataflow runtime

services/retrieval
  -> owns online retrieval execution in Java
```

这三者之间是“平台拥有真相，RAGFlow 提供引擎”，不是“平台从属于 RAGFlow 产品模型”。

## 9. 一句话

`upstream/ragflow` 在当前项目里最合适的身份，是一个被平台边界围住的解析与工作台引擎，而不是平台本体。

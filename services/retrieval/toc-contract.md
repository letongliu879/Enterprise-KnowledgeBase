# TOC Contract

`retrieval_by_toc` 在 Java 侧不直接复用 RAGFlow 的运行时实现，但它依赖的投影契约需要先补齐。  
本文件定义 `services/retrieval` 当前采用的 `document_toc` projection 结构。

## 文件位置

通过配置指定：

- `retrieval.data.document-toc-file`

配置文件位置：

- `services/retrieval/src/main/resources/application.yaml`

## 记录格式

`document_toc` 使用 JSONL，一行一个 TOC 节点。

字段定义：

- `tenant_id`
  租户 ID
- `collection_id`
  collection ID
- `final_doc_id`
  文档 ID
- `toc_node_id`
  当前 TOC 节点 ID
- `parent_toc_node_id`
  父 TOC 节点 ID，没有则为空字符串
- `level`
  节点层级，直接按字符串存
- `title`
  当前 TOC 标题
- `toc_path`
  从根到当前节点的路径数组
- `linked_chunk_ids`
  当前 TOC 节点关联的 chunk ID 列表

最小示例：

```json
{
  "tenant_id": "tnt_default",
  "collection_id": "col_policy",
  "final_doc_id": "doc_expense_policy",
  "toc_node_id": "toc_reimbursement",
  "parent_toc_node_id": "",
  "level": "1",
  "title": "Reimbursement",
  "toc_path": ["Expense Policy", "Reimbursement"],
  "linked_chunk_ids": ["chk_policy_child_0002", "chk_policy_parent_0001"]
}
```

## Java 侧执行语义

当前 `retrieval_by_toc` 对齐 RAGFlow 的主思路：

1. 先在当前检索结果里找“得分总和最高”的文档
2. 只读取这个文档的 TOC 节点
3. 根据 query 和 TOC 标题 / path 做相关性选择
4. 把命中的 `linked_chunk_ids` 回灌到结果集
5. 再进入 `retrieval_by_children`

## 当前开关

默认开启：

- `retrieval.search.enable-ragflow-toc-aggregation=true`

相关参数：

- `retrieval.search.ragflow-toc-top-n=6`
- `retrieval.search.ragflow-toc-min-score=0.3`

## 当前边界

当前 Java 版已经有 TOC 契约和 `retrieval_by_toc` 主链，但 TOC 节点选择还不是 RAGFlow 那种 chat model 打分版。

当前实现是：

- 结构与链路先对齐
- TOC 节点相关性先用本地 query / title / path overlap 选择

后续如果要进一步贴近 RAGFlow，需要再补：

- chat model 接入 retrieval
- `relevant_chunks_with_toc` 风格的 TOC 节点评分器

# indexing 对外接口契约

## Inbound（indexing 接收的请求）

### POST /internal/parse-previews — 请求预解析
`ParsePreviewRequestedCommand`:
```
request_id, tenant_id, collection_id, source_file_id, source_binary_ref,
filename, mime_type, parser_id (opt), collection_parser_id (opt),
collection_parser_config, parser_config, content_class_hint,
source_system, metadata, trace_id
```
返回 `202 Accepted` + `ParsePreviewAccepted`（含 `parse_snapshot_id`）

### GET /internal/parse-snapshots/{id} — 查询 ParseSnapshot
### GET /internal/parse-snapshots/{id}/chunks?page=1&page_size=50

`GET /internal/parse-snapshots/{id}/chunks` 返回字段约定：
```
items[].evidence_id, items[].doc_id, items[].content,
items[].section_path, items[].page_spans, items[].chunk_type, items[].metadata
```

备注：
- `doc_id` 对外统一使用 canonical 文档身份，优先返回 `final_doc_id`
- 如果该 ParseSnapshot 还没有关联到已发布文档，则允许回退为 `source_file_id`
- 不再把 `source_file_id` 当作已发布文档场景下的 `doc_id`

### POST /internal/index-jobs — 提交正式索引
`IndexBuildRequestedCommand`:
```
build_request_id, request_type (publish|reindex|lifecycle_tombstone),
tenant_id, collection_id, source_file_id, final_doc_id, document_version,
publish_version, visibility, source_binary_ref, parse_snapshot_id,
governance_overlay_ref, sanitized_asset_ref, canonical_asset_ref,
metadata_ref, quality_report_ref, approval_decision_ref, confirmed_tags,
source_metadata, index_profile_id, target_index_version_id,
chunk_edit_refs, idempotency_key, trace_id
```
返回 `202 Accepted`

### GET /internal/index-jobs/{job_id}
### GET /internal/indexed-documents?collection_id=&index_version=&final_doc_id=
### POST /internal/index-versions/{id}/activate
### POST /internal/index-versions/{id}/rollback
### POST /internal/index-versions/{id}/cleanup
### GET /internal/index-versions/{id}

### POST /internal/parser-profiles/validate — ParserProfile 运行时校验
无副作用，不写 admin 表、不创建 snapshot、不触发 job

### POST /internal/chunks/{evidence_id}/revisions — 创建 chunk revision
幂等（idempotency_key），404=base chunk 不存在，409=tenant/collection 不匹配
### GET /internal/chunk-revisions/{revision_id}
### POST /internal/chunk-revisions/{revision_id}/materialize

### GET /internal/chunks — ACL 过滤查询 chunks
参数: tenant_id, principal_id, collection_id(opt), principal_groups(opt)

## Outbound（indexing 发出的请求）

| 方向 | 端点 | 说明 |
|------|------|------|
| -> retrieval | POST /internal/index-projections/sync | 同步 index projection（full_replace 模式） |
| -> retrieval | POST /internal/cache/purge | 激活或 revision 物化后清理检索缓存 |
| -> external chat LLM | POST {chat_base_url}/chat/completions | auto_keywords/auto_questions/metadata/tagging/TOC |
| -> external embedding | POST {embedding_base_url}/embeddings | 向量化，批量分片 |

## 关键数据模型

### IndexBuildRequestType
`publish`: build + activate 原子操作
`reindex`: build + activate 原子操作
`lifecycle_tombstone`: 仅构建，不激活

### IndexVersionStatus
`BUILDING -> READY -> ACTIVE -> INACTIVE -> DISCARDED`
`ACTIVE -> ROLLED_BACK`

### ParserProfile embedding_text_policy
`display_text` / `question_kwd` / `display_text_with_authors` / `display_text_with_section_path`

### 支持的 parser_id
`naive`, `presentation`, `paper`, `qa`, `table`, `picture`, `audio`, `email`, `manual`, `resume`

## parser_config 关键字段（来自 upstream_parser_config.py）
| 字段 | 默认值 | 说明 |
|------|--------|------|
| `chunk_token_num` | 512 | 最大 token 数，>8192 warning，<128 warning |
| `delimiter` | `\n` | 切分分隔符 |
| `layout_recognize` | `DeepDOC` | 布局识别引擎 |
| `auto_keywords` | 0 | >0 时自动提取关键字（topn） |
| `auto_questions` | 0 | >0 时自动提取问题（topn） |
| `enable_metadata` | false | 是否启用 LLM metadata 提取 |
| `tag_kb_ids` | [] | 内容打标的 kb 列表 |
| `available_tags` | [] | 可用标签列表 |
| `toc_extraction` | false | 是否提取目录（仅 naive parser） |
| `table_context_size` | 0 | 表格上下文行数 |
| `image_context_size` | 0 | 图片上下文行数 |
| `raptor.use_raptor` | true | RAPTOR 摘要（naive 默认开，其他默认关） |
| `graphrag.use_graphrag` | true | GraphRAG（naive 默认开，其他默认关） |
| `filename_embd_weight` | 0.1 | embedding title/body 混合权重 |

## 配置环境变量（INDEXING_*）
`INDEXING_CHAT_API_KEY`, `INDEXING_CHAT_BASE_URL`, `INDEXING_CHAT_MODEL`
`INDEXING_EMBEDDING_API_KEY`, `INDEXING_EMBEDDING_BASE_URL`, `INDEXING_EMBEDDING_MODEL`
`INDEXING_EMBEDDING_BATCH_SIZE` (default 16)
`INDEXING_BACKEND_MODE` (noop|hybrid)
`INDEXING_OPENSEARCH_URL`, `INDEXING_QDRANT_URL`
`INDEXING_REQUIRE_LIVE_BACKENDS` (bool)
`RETRIEVAL_SERVICE_URL`（可选，用于 sync projection + cache purge）

## 错误与幂等
- `idempotency_key` 用于 job 创建和 chunk revision 创建，重复 key 返回已有结果
- index projection sync 带 command_id（UUID），retrieval 侧幂等
- cache purge fail-open：retrieval 不可达时只 warning 不阻断主流程
- 404: snapshot/job/revision 不存在
- 409: tenant/collection 与 base chunk 不匹配
- 500: materialization 运行时错误

## 输出字段参考（ChunkRecord body 写入 OpenSearch/Qdrant）
写入 payload 含 80+ 字段，详见 `asset_bundle.py` 中的 `OpenSearchIndexRecord.body` 和 `QdrantPointRecord.payload`。

关键分组：
- **id 字段**: chunk_id / kb_id / doc_id / final_doc_id / tenant_id / collection_id / index_version_id
- **文本字段**: display_text / content_with_weight / vector_text / title_text / embedding_text
- **分词字段**: content_ltks / content_sm_ltks / title_tks / title_sm_tks / important_tks / question_tks / authors_tks
- **定位字段**: position_int / page_num_int / top_int / section_path / page_spans
- **控制字段**: available_int / removed_kwd / visibility / published_document_state
- **权限字段**: allowed_principal_ids / allowed_groups
- **引用字段**: citation_payload / source_block_ids / source_id

## Wire 约束补充
- ParseSnapshot chunk 预览、chunk 查询、检索证据等所有对外 wire 字段统一使用 `doc_id`
- `final_doc_id` 可以保留为 indexing 内部持久化和治理字段名，但不应继续作为新对外接口字段

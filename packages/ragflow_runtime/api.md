# ragflow_runtime 对外接口契约

## 端口/协议 (`ports/`)

| Protocol | 位置 | 方法 | 说明 |
|----------|------|------|------|
| `AssetResolverPort` | `ports/asset_resolver.py:15` | `resolve(asset_ref) -> ResolvedAsset` | 解析资产引用为文件+字节 |
| `ModelProviderPort` | `ports/model_provider.py:15` | `get_model(request: ModelRequest) -> object\|None` | 获取运行时模型 |
| `ProgressSinkPort` | `ports/progress_sink.py:6` | `emit(progress, message)` | 消费解析/分块进度 |
| `PipelineLogSinkPort` | `ports/pipeline_log_sink.py:6` | `append(component_id, progress, message)` | 持久化数据流日志 |

| DataClass | 位置 | 字段 |
|-----------|------|------|
| `ResolvedAsset` | `ports/asset_resolver.py:7` | `asset_ref`, `filename`, `suffix`, `bytes_data` |
| `ModelRequest` | `ports/model_provider.py:7` | `tenant_id`, `model_type`, `model_name?`, `language?` |

### 默认适配器 (`adapters/`)

| 适配器 | 位置 | 说明 |
|--------|------|------|
| `NoOpModelProvider` | `adapters/noop_model_provider.py` | 返回 None（fallback） |
| `NoOpProgressSink` | `adapters/noop_progress_sink.py` | 静默消费 |

## 通用常量 (`common/constants.py`)

| 枚举 | 成员示例 |
|------|----------|
| `RetCode` (IntEnum) | `SUCCESS=0`, `EXCEPTION_ERROR=100`, `NOT_FOUND=404` |
| `LLMType` (StrEnum) | `chat`, `embedding`, `speech2text`, `image2text`, `rerank`, `tts`, `ocr` |
| `ParserType` (StrEnum) | `presentation`, `manual`, `paper`, `resume`, `qa`, `table`, `naive`, `picture`, `audio`, `email` |
| `TaskStatus` (StrEnum) | `UNSTART="0"`, `RUNNING="1"`, `DONE="3"`, `FAIL="4"` |
| `FileSource` (StrEnum) | `LOCAL`, `KNOWLEDGEBASE`, `NOTION`, `CONFLUENCE`, `SLACK`, `GMAIL`, ... (30+) |
| `Storage` (Enum) | `MINIO`, `AZURE_S3`, `AWS_S3`, `OSS`, `GCS` |

## LLM 工具 (`LLMBundle` in `__init__.py`)

`ragflow_runtime.LLMBundle` 是平台托管的 LLM 封装，通过 `load_indexing_config()` 自动获取配置。

```python
class LLMBundle:
    def __init__(self, tenant_id=None, model_config=None, lang=None)
    def encode(self, texts: str | list[str]) -> tuple[list[list[float]], int]
    async def async_chat(self, system, history=None, gen_conf=None) -> str
```

- `encode()`: 调用外部 embedding API（`{base_url}/embeddings`），fallback 到 SHA-256 确定性伪向量（dev/offline 模式）
- `async_chat()`: 调用外部 chat API（`{base_url}/chat/completions`），fallback 到启发式响应（dev/offline 模式）
- 配置来源：`load_indexing_config()` → `INDEXING_*` 环境变量，支持多名字 fallback

## 文档解析与分块 (`rag_app/`)

所有 parser 通过统一入口调用：

```python
from ragflow_runtime.rag_app import naive, paper, presentation, manual, qa, table, picture, audio, email, resume

# 通用入口:
result = naive.chunk(filename, binary, parser_config, ...)
# 或通过 parser_id 派发:
from ragflow_runtime.common.constants import ParserType
```

### parser_config 标准字段

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `chunk_token_num` | 512 | 最大 token 数（>8192 warning，<128 warning） |
| `delimiter` | `\n` | 切分分隔符 |
| `layout_recognize` | `DeepDOC` | 布局识别引擎 |
| `auto_keywords` | 0 | LLM 自动提取关键字 topn |
| `auto_questions` | 0 | LLM 自动提取问题 topn |
| `enable_metadata` | false | LLM metadata 提取 |
| `toc_extraction` | false | 提取目录（仅 naive） |
| `raptor.use_raptor` | true | RAPTOR 摘要（naive 默认开） |
| `graphrag.use_graphrag` | true | GraphRAG（naive 默认开） |
| `filename_embd_weight` | 0.1 | embedding title/body 混合权重 |

## 深度文档解析 (`deepdoc/`)

### Parser (`deepdoc/parser/`)

| Parser 类 | 位置 | 格式 |
|-----------|------|------|
| `RAGFlowPdfParser` | `deepdoc/parser/pdf_parser.py:17` | PDF（2079 行，含布局/OCR/表格） |
| `RAGFlowDocxParser` | `deepdoc/parser/docx_parser.py` | DOCX |
| `RAGFlowExcelParser` | `deepdoc/parser/excel_parser.py` | XLSX/CSV |
| `RAGFlowHtmlParser` | `deepdoc/parser/html_parser.py` | HTML |
| `RAGFlowMarkdownParser` | `deepdoc/parser/markdown_parser.py` | Markdown |
| `RAGFlowJsonParser` | `deepdoc/parser/json_parser.py` | JSON |
| `RAGFlowTxtParser` | `deepdoc/parser/txt_parser.py` | 纯文本 |
| `RAGFlowPptParser` | `deepdoc/parser/ppt_parser.py` | PPTX |
| `RAGFlowEpubParser` | `deepdoc/parser/epub_parser.py` | EPUB |
| `VisionFigureParser` | `deepdoc/parser/figure_parser.py` | 图片（Vision LLM 描述） |
| `DoclingParser` | `deepdoc/parser/docling_parser.py` | PDF（IBM Docling） |
| `MinerUParser` | `deepdoc/parser/mineru_parser.py` | PDF（MinerU） |
| `PaddleOCRParser` | `deepdoc/parser/paddleocr_parser.py` | 图片/PDF（PP-OCRv5/VL） |
| `TCADPParser` | `deepdoc/parser/tcadp_parser.py` | PDF（腾讯云 ADAP） |
| `OpenDataLoaderParser` | `deepdoc/parser/opendataloader_parser.py` | 通用（OpenDataLoader） |

### Vision 引擎 (`deepdoc/vision/`)

| 类 | 位置 | 说明 |
|----|------|------|
| `OCR` | `deepdoc/vision/ocr.py` | ONNX 文本检测（751 行） |
| `Recognizer` | `deepdoc/vision/recognizer.py` | ONNX 识别器（442 行） |
| `LayoutRecognizer` | `deepdoc/vision/layout_recognizer.py` | 页面布局分类（461 行） |
| `TableStructureRecognizer` | `deepdoc/vision/table_structure_recognizer.py` | 表格结构检测（612 行） |

## 分块引擎 (`chunking/`)

| 模块 | 位置 | 说明 |
|------|------|------|
| `token_chunker` | `chunking/token_chunker.py` | `tokenize()` / `naive_merge()` / `tokenize_table()` |
| `title_chunker/common` | `chunking/title_chunker/common.py` | `token_count()`, `resolve_target_level()` |
| `title_chunker/group_chunker` | `chunking/title_chunker/group_chunker.py` | `build_section_ids()` |
| `title_chunker/hierarchy_chunker` | `chunking/title_chunker/hierarchy_chunker.py` | `_ChunkNode`, `build_tree()`, `get_paths()` |

## NLP 管道 (`rag_nlp/`)

| 模块 | 说明 |
|------|------|
| `rag_nlp.RagTokenizer` | Infinity SDK 或 fallback regex 令牌化 |
| `rag_nlp.Search` | Vector + Keyword 混合搜索（969 行） |
| `rag_nlp.FulltextQueryer` | BM25 布尔查询构建（246 行） |
| `rag_nlp.TermWeight` | TF-IDF + NER 术语加权（247 行） |
| `rag_nlp.Synonym` | 自定义词典 + WordNet 同义词扩展 |

## Prompt 模板 (`rag_prompts/`)

| 模块 | 说明 |
|------|------|
| `load_prompt(name) -> str` | 从 `rag_prompts/*.md` 加载 prompt 模板 |
| `chunks_format(...)` | 格式化 chunks 为 LLM 输入 |
| `get_reranked_answer(...)` | 重排序 + 上下文组装（Jinja2） |

## doc_store 后端 (`common/doc_store/`)

| 后端 | 连接池类 | Base 类 |
|------|----------|---------|
| Elasticsearch | `ElasticSearchConnectionPool` | `ESConnectionBase` |
| Infinity | `InfinityConnectionPool` | `InfinityConnectionBase` |
| OceanBase (MySQL) | `OceanBaseConnectionPool` | `OBConnectionBase` |

统一查询原语（`doc_store_base.py`）：
- `MatchTextExpr` / `MatchDenseExpr` / `MatchSparseExpr`
- `FusionExpr` / `OrderByExpr`
- `DocStoreConnection` ABC

## 数据源连接器 (`common/data_source/`)

23 个连接器（MIT 协议，来自 Onyx）：
`S3/R2/GCS/OCI` `RSS` `Slack` `Gmail` `Notion` `Confluence` `Discord` `Dropbox` `SharePoint` `Teams`
`Moodle` `Airtable` `DingTalk` `Asana` `IMAP` `Zendesk` `SeaFile` `RDBMS` `WebDAV` `REST API`
`GitHub` `GitLab` `Bitbucket` `Jira` `Google Drive` `Box`

接口：`LoadConnector` / `PollConnector` / `FingerprintConnector` / `CheckpointedConnectorWithPermSync`

## 关键环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RAG_PROJECT_BASE` | - | 运行时资源根目录（deepdoc ONNX 模型、conf 配置等） |
| `DOC_ENGINE` | elasticsearch | 文档存储后端: `elasticsearch`/`infinity`/`oceanbase` |
| `EMBEDDING_BATCH_SIZE` | 16 | Embedding 批大小 |
| `MAXIMUM_PAGE_NUMBER` | 100000 | 解析最大页数 |
| `PADDLEOCR_*` | - | PaddleOCR 配置（API URL / Token / Algorithm） |
| `MINERU_*` | - | MinerU 配置（APISERVER / BACKEND / OUTPUT_DIR） |
| `DOCLING_SERVER_URL` | - | Docling 服务 URL |
| `TCADP_OUTPUT_DIR` | - | 腾讯云 ADAP 输出目录 |
| `OPENAI_API_KEY` | - | LLM API Key fallback |
| `OPENAI_BASE_URL` | - | LLM Base URL fallback |

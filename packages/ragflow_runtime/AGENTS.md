# ragflow_runtime — 文档解析与分块运行时

## 定位
ragflow_runtime 是基于 RAGFlow（Apache 2.0）衍生的受控运行时库，负责所有文档格式的解析（parsing）和分块（chunking）。indexing-service 通过此库实现从原始文件到结构化 chunk 的全链路。

**不做的事**：不负责索引写入、不负责治理/租户隔离/可见性决策、不对外提供查询 API、不管理文档生命周期。

## 边界原则
- **六边形架构**：`ports/` 定义平台接口（Protocol），`adapters/` 提供 no-op 默认实现
- **兼容性别名**：`__init__.py` 安装 `sys.modules` 别名，使上游 `import rag.*` 代码可正常运行（长期方向是逐步移除别名）
- **Parser 策略**：每种文档类型有独立的 parser 实现（`rag_app/{naive,paper,presentation,...}.py`）
- **Chunking 两级**：`chunking/token_chunker.py` 通用 token 级切分 + `chunking/title_chunker/` 基于 title 结构的分块
- **深度文档解析**：`deepdoc/` 包含 ONNX 模型驱动的高精度 PDF 解析（布局/OCR/表格）
- **doc_store 多后端**：Elasticsearch / Infinity / OceanBase 三种向量/全文检索引擎抽象
- **外部解析器集成**：Docling（IBM）、MinerU、PaddleOCR、腾讯云 ADAP、OpenDataLoader
- **LLM Provider**：40+ 大模型供应商配置（`resources/conf/models/*.json`）

## 核心数据流
```
Source file (PDF/DOCX/PPT/图片/音频/邮件...)
  │
  ▼ Parser Selection (based on parser_id / mime_type)
  ├── deepdoc.parser.XXX (PDF/Ppt/Docx/Excel/Html/Markdown/Json/Txt/Epub)
  ├── deepdoc.vision (OCR + Layout + Table recognition) —— 用于 PDF/图片
  ├── 外部 Parser: MinerU / Docling / PaddleOCR / TCADP / OpenDataLoader
  └── figure_parser (Vision LLM 为图片生成描述)
  │
  ▼ Rag App Chunking (rag_app/{naive,paper,manual,...}.py)
  ├── 按文档类型选择 chunking 策略
  ├── title_chunker 基于标题层级构建树结构
  ├── token_chunker token 数约束切分
  └── 产: list[Chunk]（含 section_path / position / citation 等元数据）
  │
  ▼ NLP Pipeline (rag_nlp/)
  ├── Tokenization (RagTokenizer → Infinity SDK / regex fallback)
  ├── Term Weighting (TF-IDF + NER)
  ├── Synonym Expansion (custom dict + WordNet)
  ├── Query Construction (BM25-style with field boosting)
  └── Search Dealer (Vector + Keyword hybrid search)
```

## 关键对象
- `LLMBundle`：平台托管的 LLM 封装（`__init__.py:171`），`encode()` / `async_chat()` 对接 reality_rag_contracts 的配置加载
- `RagTokenizer`：令牌化器（`rag_nlp/rag_tokenizer.py`）
- `RetCode`：通用返回码枚举（`common/constants.py:45`）
- `TaskStatus` / `ParserType` / `LLMType`：上游 RAGFlow 的状态/类型枚举
- `BaseConverter` → `RAGFlowConverter`：外部转换器策略（`intake_runtime` 使用）
- ports: `AssetResolverPort`, `ModelProviderPort`, `ProgressSinkPort`, `PipelineLogSinkPort`
- doc_store: `ESConnectionBase`, `InfinityConnectionBase`, `OBConnectionBase`（连接池单例）

## Rag App 解析器/分块器

| Rag App | 位置 | 文档类型 | 特殊行为 |
|---------|------|----------|----------|
| `naive` | `rag_app/naive.py` | 通用文本 | PARSERS dict 派发，支持 RAPTOR/GraphRAG |
| `presentation` | `rag_app/presentation.py` | PPT/演示文档 | section_path = `[title, "Slide N"]` |
| `paper` | `rag_app/paper.py` | 学术论文 | metadata.authors + important_kwd |
| `manual` | `rag_app/manual.py` | 产品手册 | YOLOv10 layout + section_paths |
| `qa` | `rag_app/qa.py` | QA 问答对 | section_path = `[title, question_kwd]` |
| `table` | `rag_app/table.py` | 表格/CSV | doc_metadata 聚合列值 |
| `picture` | `rag_app/picture.py` | 图片/视频 | OCR + vision |
| `audio` | `rag_app/audio.py` | 音频 | 语音转文本 |
| `email` | `rag_app/email.py` | .eml 邮件 | 结构化提取 |
| `resume` | `rag_app/resume.py` | 简历 | SmartResume (arXiv:2510.09722) |

## 约束
- 不要直接调用 `deepdoc.parser.XXX` 的底层方法 —— 必须通过 `rag_app.{parser_id}.chunk()` 入口
- 不要绕过 `LLMBundle` 直接调用 LLM API —— 所有 LLM 调用通过 LLMBundle（统一管理配置和 fallback）
- 不要在生产代码中使用 `settings.py` 的全局单例 —— 优先通过 `reality_rag_contracts` 的 `load_indexing_config()` 获取配置
- 外部解析器（MinerU/Docling/PaddleOCR/TCADP）需要额外环境配置（URL/API Key 等），不要假设它们默认可用
- `sys.modules` 别名（`rag.*` / `common.*` / `deepdoc.*` / `api.db.*`）是临时兼容方案 —— 不要在新代码中依赖它们
- `chunking/title_chunker/` 的树状分块仅适用于有标题层次结构的文档（manual/paper 等）
- vision 模型文件（ONNX）需要从 HuggingFace `InfiniFlow/deepdoc` 下载，或通过 `RAG_PROJECT_BASE` 环境变量指定本地路径
- 数据源连接器（`common/data_source/`）来自 Onyx（MIT License），是独立的 connector 层，不要混入解析流程
- `deepdoc/parser/resume/` 是独立的简历解析流水线，通过 `refactor()` 函数调用

# RAGFlow Query Strategies

本文件记录 `services/retrieval` 当前已经接入的 RAGFlow 风格 query 前处理策略，以及对应的输入契约与开关位置。

## 当前顺序

Java 侧当前执行顺序按下面的链路进入检索主链：

1. `meta_data_filter`
2. `cross_languages`
3. `keyword extraction`
4. recall / fusion / rerank / cutoff
5. TOC / children 聚合

这和 RAGFlow 的总体顺序是一致的：先处理 query 和 doc scope，再进入 recall。

## 1. meta_data_filter

请求字段：

- `meta_data_filter`

支持三种模式：

- `manual`
- `auto`
- `semi_auto`

当前状态：

- `manual` 已经生效
- `auto` / `semi_auto` 已经接入 prompt 驱动入口
- 没配 live prompt model 时安全降级，不会瞎生成条件

开关：

- `retrieval.search.enable-ragflow-metadata-auto-filter=true`

说明：

- 这个开关只控制 `auto` / `semi_auto`
- `manual` 不依赖 LLM，默认就会执行

## 2. cross_languages

请求字段：

- `cross_languages`

当前状态：

- 请求契约和调用顺序已接入
- 配了 live prompt model 时执行翻译扩展
- 没配时安全降级为原 query

开关：

- `retrieval.search.enable-ragflow-cross-languages=true`

## 3. keyword extraction

请求字段：

- `keyword`

当前状态：

- 请求契约和调用顺序已接入
- 配了 live prompt model 时会把生成关键词追加回 query
- 没配时安全降级

开关：

- `retrieval.search.enable-ragflow-keyword-extraction=true`

参数：

- `retrieval.search.ragflow-keyword-top-n=3`

## 4. TOC selector

当前状态：

- `document_toc` projection 契约已接入
- TOC LLM selector 入口已接入
- 配了 live prompt model 时走 prompt 打分
- 没配时退回本地 overlap selector

开关：

- `retrieval.search.enable-ragflow-toc-aggregation=true`
- `retrieval.search.enable-ragflow-toc-llm-selector=true`

参数：

- `retrieval.search.ragflow-toc-top-n=6`
- `retrieval.search.ragflow-toc-min-score=0.3`

## 5. Prompt Backend

这几类策略共用一个 prompt model backend。

默认关闭：

- `retrieval.backends.live-prompt-strategies-enabled=false`

需要配置：

- `retrieval.backends.prompt-model-base-url`
- `retrieval.backends.prompt-model-api-key`
- `retrieval.backends.prompt-model-name`

当前客户端实现：

- OpenAI-compatible `/chat/completions`

## 当前边界

这一层的原则很明确：

- 先把 RAGFlow 的策略顺序、输入契约、开关和主链位置接上
- 再用 prompt backend 驱动真正的 LLM 行为
- 在没配 LLM 的环境里，只允许安全降级，不允许发明一套替代策略冒充 RAGFlow 原版

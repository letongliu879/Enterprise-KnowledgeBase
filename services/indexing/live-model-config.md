# Live Model Config

`services/indexing` 现在支持直接用真实外部模型跑 preview、metadata、tagging、toc 和 embedding。

当前真实配置约定：

- `INDEXING_CHAT_BASE_URL=https://api.deepseek.com`
- `INDEXING_CHAT_MODEL=deepseek-v4-flash`
- `INDEXING_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1/embeddings`
- `INDEXING_EMBEDDING_MODEL=BAAI/bge-m3`

注意：

- 不要把 SiliconFlow 的 embedding 模型写成裸的 `bge-m3`。当前应使用 `BAAI/bge-m3`。
- 兼容层会把上游传入的占位名 `chat` / `embedding` 自动归一到真实模型名，但正式 `.env` 仍建议直接写真实值。
- `.env.example` 已同步更新为 `BAAI/bge-m3`。

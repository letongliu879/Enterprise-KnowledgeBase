# Enterprise KnowledgeBase

Enterprise KnowledgeBase is an enterprise knowledge platform for governed RAG and MCP services.

This project is the revised version of `Reality-RAG`. It keeps the same high-level service architecture, while changing the upstream integration strategy:

- governance, lifecycle, and retrieval boundaries remain platform-owned
- RAGFlow is used directly for document parsing and chunking runtime capability
- RAGFlow is not the governance source of truth

Architecture entry:

- [Top-level architecture](./docs/architecture.md)
- [Project overview](./docs/project-overview.md)
- [ParseSnapshot architecture](./docs/parse-snapshot-architecture.md)
- [Role of upstream/ragflow](./docs/upstream-ragflow-role.md)
- [What to keep from Reality-RAG](./docs/reality-rag-lessons.md)
- [Intake pipeline design](./services/intake-pipeline/intake-pipeline.md)
- [RAGFlow source isolation map](./docs/ragflow-source-isolation.md)

Current repository focus:

- `contracts/`: canonical service contracts
- `packages/contracts`: Python runtime contract package
- `packages/persistence`: persistence models and repositories
- `packages/documents`: shared document-domain package
- `services/intake-pipeline`: intake, governance, approval, publishing, lifecycle
- `services/indexing`: parse preview, ParseSnapshot, chunking, embedding, index materialization
- `services/retrieval`: Java retrieval mainline with RAGFlow/ContextWeaver-inspired strategies
- `services/workbench-api`: workbench-facing parse/chunk API seam
- `upstream/ragflow`: source fork for parsing/chunking/workbench runtime

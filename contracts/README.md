# Contracts

`contracts/` is the canonical cross-service contract source for the final Reality-RAG architecture.

- `openapi/` defines HTTP ingress contracts.
- `schemas/` defines core DTO and state schemas.
- `events/` defines event envelope and event payload schemas.
- `examples/` provides example payloads used by contract tests.
- `compatibility/` records compatibility rules and evolution notes.

These files are authoritative for cross-service names and payload shape. Service-local models may wrap them, but they must not redefine them incompatibly.

Current repository status:

- Some services still keep local mirrored DTO/model definitions because code generation is not fully wired yet.
- These local mirrors are transitional only; they are not independent contract owners and must not evolve field shape on their own.
- Any contract change must land in `contracts/` first, then be propagated into local mirrors.
- Until generation is fully wired, every local mirror must be treated as `contracts/`-validated compatibility scaffolding, not as a parallel schema source.

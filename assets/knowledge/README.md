# Knowledge Base Index

## Harvested Knowledge (Long-term)

> **Path**: `assets/knowledge/harvested/` (via `references.yaml: harvested_knowledge.dir`)

Long-term knowledge extracted from development sessions, ingested into Neural Matrix vector DB.

| Date     | Category     | Title                          | File                                                                                                                           |
| -------- | ------------ | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| 20260102 | architecture | Phase 11: The Neural Matrix Im | [`20260102-architecture-phase-11:-the-neural-matrix-im.md`](harvested/20260102-architecture-phase-11:-the-neural-matrix-im.md) |
| 20260102 | architecture | Neural Matrix Rag Implementati | [`20260102-architecture-neural matrix rag implementati.md`](harvested/20260102-architecture-neural matrix rag implementati.md) |
| 20260102 | architecture | Implementing The Harvester Mod | [`20260102-architecture-implementing the harvester mod.md`](harvested/20260102-architecture-implementing the harvester mod.md) |
| 20260102 | architecture | Implementing Self Hosted Vecto | [`20260102-architecture-implementing self-hosted vecto.md`](harvested/20260102-architecture-implementing self-hosted vecto.md) |

## Storage Strategy

| Type | Path | Management |
| ---- | ---- | ---------- |
| **Harvested Knowledge** | `assets/knowledge/harvested/` | Long-term, version controlled |
| **Cache** | `.cache/` | Temporary, safe to delete |
| **Memory** | `.cache/memory/` | Runtime data (routing_feedback.json, active_context/) |
| **Vector DB** | `.cache/chromadb/` | ChromaDB vector index |

# LinkGraph vs Librarian: Roles and How to Use

All project markdown is indexed by **LinkGraph** first. The **Librarian** has a different role: it builds the **vector/semantic layer** for that content (or a subset). This doc clarifies the split and how to use each.

## Summary

| Component     | Role                                        | What it indexes                | You use it for                                              |
| ------------- | ------------------------------------------- | ------------------------------ | ----------------------------------------------------------- |
| **LinkGraph** | Primary index for all project markdown      | All `.md` under notebook dir   | Link reasoning, link_graph_search, link_graph_hybrid_search |
| **Librarian** | Vector ingestion for semantic/hybrid search | Paths in `knowledge_dirs` only | recall, vector leg of link_graph_hybrid_search              |

- **LinkGraph** = “which markdown exists” + link graph + structural search.
- **Librarian** = “chunk and embed a subset” → powers semantic search (recall) and the vector side of link_graph_hybrid_search.

## LinkGraph: Primary Markdown Index

- **Config**: `references.yaml` uses LinkGraph keys (`link_graph.notebook`, `link_graph.harvested`) for the LinkGraph source set.
- In the knowledge skill, LinkGraph uses **project root** as the notebook dir, so **all** markdown under the repo (including `docs/`, `assets/knowledge/`, `.data/harvested/`) is indexed.
- **Use**:
  - `knowledge.link_graph_search` – link-based reasoning over notes.
  - `knowledge.link_graph_hybrid_search` – link graph + vector.
  - `knowledge.link_graph_links`, `link_graph_stats`, etc. – all operate on this same link graph index.

No extra index step is needed beyond having the notebook dir set (project root in the skill).

## Librarian: Vector Layer for Semantic Search

- **Config**: `references.yaml` → `knowledge_dirs` (paths + globs). Only these paths are chunked and embedded.
- **Output**: Writes to LanceDB (`knowledge_chunks` table). This is the store used by:
  - **knowledge.recall** – semantic + keyword hybrid over the vector store.
  - **link_graph_hybrid_search** – the “vector” leg queries this same store.
- **Use**:
  - Run **`omni sync knowledge`** (or equivalent ingest) to refresh the vector index from `knowledge_dirs`.
  - Then use **knowledge.recall** when you want “find by meaning” or **link_graph_hybrid_search** when you want graph + semantic together.

So Librarian does **not** decide “which markdown exists”; LinkGraph does that. Librarian decides **which of that content gets vectorized** and provides the semantic search backend.

## How to Use in Practice

1. **All markdown**  
   Already covered by LinkGraph (notebook = project root). Use **link_graph_search** or **link_graph_hybrid_search** to search/follow links.

2. **Semantic search (“像…的内容” / “和 X 相关的文档”)**
   - Ensure the content you care about is under **knowledge_dirs** (e.g. `docs`, `assets/knowledge`).
   - Run **`omni sync knowledge`** to (re)build the vector index.
   - Use **knowledge.recall** or **link_graph_hybrid_search** (hybrid = link graph + recall).

3. **Research reports (e.g. `.data/harvested`)**
   - Indexed by **LinkGraph** via `link_graph.harvested` (notebook = project root).
   - To also have them in **semantic** search, add `.data/harvested` back to **knowledge_dirs** and run `omni sync knowledge`. If you only want link-based search over them, LinkGraph alone is enough.

## One-Line Takeaway

- **LinkGraph** = primary index for all project markdown; use for structure and links.
- **Librarian** = vector pipeline for a subset (`knowledge_dirs`); use for semantic recall and the vector half of link_graph_hybrid_search.

# How to Query and Locate Ingested Papers via MCP

This guide describes the end-to-end flow: user asks for papers (e.g. "RAG Anything" or "ing-related papers"), and the agent uses MCP knowledge tools to find and cite them.

---

## Flow Overview

```
User: "Find me papers about RAG Anything / ingest-related papers"
        │
        ▼
Agent calls MCP knowledge tools (no CLI)
        │
        ├── knowledge.recall(query="RAG Anything document parsing paper", limit=5)
        │   → Returns chunks with content, source, score from vector store
        │
        └── knowledge.search(query="RAG anything ing paper", mode="hybrid")
            → Returns merged LinkGraph + vector results; vector hits are from ingested docs
        │
        ▼
Agent interprets results and answers user
        → "The paper you ingested (e.g. arxiv 2510.12323) is in the knowledge base.
           Relevant snippets: [content]. The document was stored from .artifacts/2510.12323.pdf."
```

---

## MCP Tools to Use

| Tool                 | When to use                                                                                  | Example                                                     |
| -------------------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **knowledge.recall** | Semantic search over the vector store (ingested PDFs, markdown, etc.)                        | Query: "RAG Anything universal framework overview abstract" |
| **knowledge.search** | Hybrid (LinkGraph + vector) or keyword-only; good when you want both notes and ingested docs | Query: "RAG anything ing paper", mode: "hybrid"             |

Both can surface content from an ingested PDF. Recall returns `content`, `source`, `score`; search returns merged results with `source` and reasoning.

### Action-based recall (avoids MCP timeout)

For long content, a single `knowledge.recall` with default `chunked=True` runs preview → fetch → all batches in one call, which can time out and cause memory accumulation. Use **one step per MCP call** like `git.smart_commit`:

1. **start** – `knowledge.recall(query="...", chunked=True, action="start")` → preview only, returns `session_id` and `batch_count` (no full fetch; avoids memory spike).
2. **batch** – `knowledge.recall(session_id="<from start>", action="batch", batch_index=0)` … then `batch_index=1`, etc. → each call lazy-fetches and returns one batch (no full state in memory).
3. **full_document** – `knowledge.recall(chunked=True, action="full_document", source="2601.03192.pdf")` → returns **all chunks** for that document, sorted by `chunk_index`. Use when you need the **complete paper with no omission** (semantic search returns top-N and may miss chunks).

Each batch response is small; the LLM reads slice by slice. This avoids memory accumulation and token limits.

---

## How to "Locate" the Paper

- **After ingest**: The PDF is chunked and stored in the knowledge vector store with metadata `source: <file_path>` (e.g. `.artifacts/2510.12323.pdf`) and `title: <filename>`.
- **In recall results**: The `source` field in the API may be the chunk ID (e.g. UUID) depending on the vector backend. To show the user "which paper" a snippet came from, the agent can:
  1. Use the **content** of the recalled chunks (e.g. "Figure 1: Overview of our proposed universal RAG framework RAG-Anything") to infer the document.
  2. If the system exposes document path in recall metadata, use that to say "from .artifacts/2510.12323.pdf (arxiv 2510.12323)".

So "locating" the paper means: run recall/search with a natural-language query about the topic, then report the matching snippets and, when available, the document path or arxiv id from metadata or context.

---

## Example: User Asks for "RAG Anything / ing-Related Papers"

1. **User**: "帮我找寻 RAG Anything 或 ing 相关的论文" (or: "Find me papers about RAG Anything or ingest-related work.")

2. **Agent** calls MCP:
   - `knowledge.recall(query="RAG Anything document parsing or ingest pipeline paper", limit=5)`
   - Optionally: `knowledge.search(query="RAG anything ing paper", mode="hybrid")`

3. **MCP returns** (example):
   - Chunks such as: "Figure 1: Overview of our proposed universal RAG framework RAG-Anything." with high score.
   - Other snippets about multimodal analysis, RAG pipelines, etc.

4. **Agent answers user**:
   - "The knowledge base contains a paper that matches your request: **RAG-Anything** (universal RAG framework). Relevant excerpts: [paste content]. This was ingested from the PDF at `.artifacts/2510.12323.pdf` (arXiv 2510.12323)."

---

## Prerequisites

- The target paper (or its PDF) must already be **ingested** via `knowledge.ingest_document` (e.g. after downloading the PDF to a local path). MCP does not ingest from URL; download first, then ingest.
- Vector store must be available (e.g. after `omni sync knowledge` or ingest_document); then recall/search work via MCP without running CLI commands.

## Prefer MCP over CLI (Cursor)

When MCP is enabled in Cursor, **prefer calling skill tools via MCP** (e.g. `knowledge.ingest_document`, `knowledge.recall`) instead of `omni skill run ...`. If the AI reports it does not see MCP tools, check: (1) MCP server is connected in Cursor settings; (2) the Composer/Agent session was started after MCP connected so the tool list is injected. **Fallback**: use CLI `omni skill run knowledge.ingest_document '{"file_path":"..."}'` or `omni knowledge recall "query"`.

## CLI: Fast path vs full skill

- **Fast path (recommended for CLI)**: `omni knowledge recall "query" [--limit N] [--json]`  
  Uses only the foundation vector store and embedding; **typically under 2s**. No kernel/skill stack.
- **Full skill**: `omni skill run knowledge.recall '{"query":"..."}'`  
  Loads full kernel and all skills (30–45s cold start); use for MCP or when you need dual-core boost (LinkGraph, KG).

## Timeouts (knowledge.recall)

- **Embedding**: Query embedding is limited by `knowledge.recall_embed_timeout_seconds` (default **18**). If the embedding service is slow or unreachable, recall falls back to a hash-based vector so the request returns within the limit (with potentially lower relevance) instead of hitting MCP client timeout.
- **Tool execution**: MCP tool calls use `mcp.timeout` from settings (default **1800** seconds / 30 min). If recall still times out at the client, use CLI `omni knowledge recall "your query" --limit 5` or increase `knowledge.recall_embed_timeout_seconds` (e.g. 25) and/or `mcp.timeout`.

---

## Limit vs preview vs full read

- **limit** = how many **items** to return (for accuracy list or batch size). Not for "how much content" to read. Use **preview** to confirm recall is right; use a **workflow** to read long content in chunks.
- **preview** (`recall(..., preview=True, snippet_chars=150)`): returns only title, source, score, and first N chars per result → use to **verify accuracy** before pulling full content.
- **Long content in chunks** (papers, manuals, long docs): Recalled content is usually long, so `knowledge.recall` **default** is the chunked workflow (preview → fetch → batches). Chunking is consumed in memory: feed `batches[i]` to the LLM in turn so each slice stays in context. Response includes `preview_results`, `batches`, `all_chunks_count`, `results`. Use `chunked=False` for single-call search only.

## Research workflow: use ingested content

To **research or analyze** any long ingested content (paper, manual, long doc):

1. **Default (chunked)**: Call `knowledge.recall(query="…")` → get `preview_results`, `batches`, `results`; use preview to confirm accuracy, then feed `batches[i]` to the LLM one batch per turn.
2. **Single-call**: `knowledge.recall(query="…", chunked=False, limit=N)` for one batch of full chunks (no workflow).
3. **If MCP recall times out**: Run `omni knowledge recall "…" --json` locally, or increase `knowledge.recall_embed_timeout_seconds`.

---

## Summary

- **Query**: Use natural-language queries with `knowledge.recall` or `knowledge.search` (hybrid).
- **Locate**: Use returned content + metadata (and, when available, document path) to tell the user which paper the snippets came from.
- **End-to-end**: Ingest PDF → User asks for papers → Agent uses MCP knowledge tools → Agent returns snippets and paper identity (path/arxiv id).

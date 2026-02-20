# Pensieve / StateLM vs Omni Long Content: Research & Integration

> **Paper**: [The Pensieve Paradigm: Stateful Language Models Mastering Their Own Context](https://arxiv.org/abs/2602.12108) (arXiv:2602.12108)  
> **Purpose**: Deep dive for long-content workflow; how to integrate “model-managed context” into our project.  
> **Method**: Use **knowledge ingest + recall only** — no web fetch. Ingest the PDF, then study it via `knowledge.recall` (default chunked).

---

## 1. How to Ingest and Study This Paper (Knowledge Ingest + Recall Only)

Use **only** the project’s knowledge pipeline: ingest the PDF, then recall with the default chunked workflow so the model can read it in memory slice by slice. Do not rely on web fetch; all content comes from ingest + recall.

### Step 1: Ingest the paper

**MCP** (recommended):

```text
knowledge.ingest_document(file_path="https://arxiv.org/pdf/2602.12108")
```

URLs are downloaded to `PRJ_DATA/knowledge/downloads`, then parsed, chunked, embedded, and stored in the vector store (and optionally graph).

**CLI** (if you prefer):

```bash
# After ensuring vector store is ready (e.g. omni sync knowledge)
uv run omni skill run knowledge.ingest_document '{"file_path":"https://arxiv.org/pdf/2602.12108"}'
```

### Step 2: Research via recall (default = chunked)

**Default behavior** is the chunked workflow: preview → fetch full chunks → split into batches. The model reads each batch in memory in turn.

**MCP**:

```text
knowledge.recall(query="Pensieve StateLM stateful context memory tools context pruning document indexing note-taking long document")
```

Returns `preview_results`, `batches`, `all_chunks_count`, `results`. Use `preview_results` to confirm you hit the right doc; then feed `batches[i]` to the LLM one batch per turn for deep reading.

**Single-call** (if you only need one batch of snippets):

```text
knowledge.recall(query="StateLM internal reasoning loop memory tools", chunked=False, limit=15)
```

### Step 3: Deeper queries after first pass

After a first read, use more specific queries to pull out design details:

- `knowledge.recall(query="StateLM context pruning document indexing note-taking training")`
- `knowledge.recall(query="StateLM long-document QA BrowseComp-Plus experiments")`
- `knowledge.recall(query="Pensieve paradigm fixed context window stateful agent")`

---

## 2. Paper Summary (Build This From Recalled Content)

After you **ingest** the paper and run **recall** (e.g. the queries in §1), use the recalled chunks to build your own summary. Do not use web fetch; the content below is an **example structure** to fill from `knowledge.recall` results.

| Aspect                 | What to extract via recall                                                                |
| ---------------------- | ----------------------------------------------------------------------------------------- |
| **Core claim**         | Model gets the “wand” to manage its own context (internal reasoning loop + memory tools). |
| **Metaphor / problem** | Pensieve: models are passive, fixed window; need agency over memory.                      |
| **Approach**           | StateLM: internal reasoning loop, state management.                                       |
| **Memory tools**       | Context pruning, document indexing, note-taking; how they are trained/used.               |
| **Results**            | Long-document QA, chat memory, deep research (e.g. BrowseComp-Plus) benchmarks.           |

**Takeaways to look for in recalled content**: (1) Long content + model-managed context (prune, index, notes). (2) Stateful, tool-using context management. (3) Role of training vs inference-time tool use.

---

## 3. Our Project’s Long-Content Design Today

| Component                      | Role                                                                                                           |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| **knowledge.recall (default)** | Chunked workflow: preview → fetch → batches; model reads **in memory** slice by slice (`batches[i]` per turn). |
| **Preview**                    | Short list (title + snippet) to verify recall accuracy before pulling full content.                            |
| **Batches**                    | Full chunks split into batches; caller feeds each batch to the LLM in turn.                                    |
| **limit / chunked=False**      | Single-call mode when you only need one batch of results.                                                      |

We already give the model “long content in slices” and consume it in memory. What we do **not** do yet: let the **model** decide what to prune, what to index, or what notes to keep (Pensieve’s “wand”).

---

## 4. Relevance to Long Content

- **StateLM** addresses the same pain: long docs, fixed context, passive context. We address “long” by **chunked recall + in-memory consumption**; they add **model-driven context management** (prune / index / notes).
- **Convergence**: Our workflow is the “supply side” (get the right chunks, in batches); Pensieve/StateLM is the “demand side” (model chooses what to keep, summarize, or drop). Integrating their ideas means giving the agent **tools** that mirror StateLM’s: e.g. “context pruning” (drop low-value chunks or summarize), “document indexing” (maintain a running index/summary), “note-taking” (persist key facts into project memory or hippocampus).

---

## 5. Learning Points (What We Can Learn)

1. **Model as context manager**  
   Instead of only “we send batches,” we can expose **memory tools** to the agent: e.g. `context_prune`, `add_to_index`, `take_note`, so the agent (or a future StateLM-style model) can manage what stays in context and what gets summarized/stored.

2. **Document indexing as a first-class action**  
   StateLM uses “document indexing” as a tool. We have knowledge graph + vector store; we could add an **agent-callable “index this doc/section”** that updates a running summary or key-points structure as the model reads batches (e.g. store in project memory or a dedicated “reading index”).

3. **Note-taking during long read**  
   As the model consumes `batches[i]`, it could call a **note-taking** skill (e.g. save to Hippocampus or project memory) so that later turns don’t need to re-read full text. This aligns with “stateful” reading.

4. **Chunked recall remains the base**  
   Our default chunked recall (preview → fetch → batches, read in memory) is the right **base**. StateLM-style tools sit on top: the model reads batches and, while reading, can prune, index, and take notes.

---

## 6. Concrete Integration Ideas for the Project

| Idea                                          | Description                                                                                                                                                                                                                                                                                          |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Memory tools in skill surface**          | Add skills or extend existing ones: e.g. `memory.context_prune` (summarize/drop low-value content), `memory.add_to_index` (update running doc index), `memory.take_note` (persist key fact). Agent uses them **during** chunked recall (after each batch or at end of read).                         |
| **2. “Reading index” for long doc**           | When the user (or agent) starts a “research this paper” flow, create a transient or persistent “reading index” (key points, sections, decisions). Update it as the model processes each batch from `knowledge.recall`.                                                                               |
| **3. Optional summarization between batches** | After feeding batch N, optionally call a summarization step and pass a short “summary so far” into the next turn so context stays bounded while preserving important content (soft form of “context pruning”).                                                                                       |
| **4. Document “Pensieve alignment”**          | In `docs/how-to/knowledge-mcp-query-paper.md` or a new doc, state that our long-content design is compatible with “model-managed context”: we provide chunked recall and in-memory consumption; future work can add StateLM-style tools so the model holds the “wand” (prune / index / note-taking). |

---

## 7. Summary

| Dimension        | StateLM / Pensieve                                    | Omni long content (current)                                   |
| ---------------- | ----------------------------------------------------- | ------------------------------------------------------------- |
| **Long content** | Model manages context via tools (prune, index, notes) | We provide chunked recall; model reads batches in memory      |
| **Agency**       | Model has the “wand”                                  | We control batching; model consumes                           |
| **Next step**    | —                                                     | Add memory tools (prune/index/notes) on top of chunked recall |

**Bottom line**: Use **knowledge ingest only** (no web fetch): `knowledge.ingest_document("https://arxiv.org/pdf/2602.12108")`, then study the paper with `knowledge.recall(...)` (default chunked). Build your summary and integration plan from the recalled content. Keep chunked recall as the default, and add agent-callable memory tools (context pruning, document indexing, note-taking) so long-content reading becomes stateful and manageable.

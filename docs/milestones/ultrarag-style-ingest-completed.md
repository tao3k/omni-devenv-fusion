# Milestone: UltraRAG-Style Ingest — Completed

**Status:** Completed  
**Scope:** Full document-ingest pipeline aligned with UltraRAG’s design, using only our stack (no UltraRAG dependency). Reference: `docs/explanation/recall-and-ingest-pdf-facts.md` §4.

---

## Summary

We implemented a complete **text** ingest pipeline: full text → single-pass chunking (Rust omni-tokenizer/tiktoken-rs) → source + chunk_index; idempotent write. Optional **PDF image extraction** saves page images to disk for downstream use; images are **not** ingested into the vector store or made available to the LLM via recall (multimodal ingest/recall is out of scope for this milestone). All phases are done; tests and docs are in place.

---

## Delivered

### Phase 1 — Idempotent ingest

| Item              | Implementation                                                                                                                              |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Replace-by-source | `delete_by_metadata_source(table_name, source)` in omni-vector (`admin_impl.rs`), exposed via PyO3 and Python `crud` / `VectorStoreClient`. |
| Ingest wiring     | `graph.py` calls `delete_by_metadata_source("knowledge_chunks", source_str)` before `add_batch` so re-ingest replaces rather than appends.  |

**Result:** Re-ingesting the same document does not create duplicate chunks; full_document recall returns one copy per chunk_index (Rust dedup as safety net).

### Phase 2 — Rust chunking API

| Item             | Implementation                                                                                                                                       |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Chunking in Rust | `chunk_text(text, chunk_size_tokens, overlap_tokens)` in omni-tokenizer (tiktoken-rs); output `Vec<(String, u32)>` (text, chunk_index).              |
| Python exposure  | `py_chunk_text` in PyO3 (`bindings/python/src/tokenizer.rs`); graph.py calls it when available.                                                      |
| Ingest default   | graph.py uses `omni_core_rs.py_chunk_text` by default; fallback to `create_chunker` when omni_core_rs unavailable; chunk_metas use Rust chunk_index. |

**Result:** Single-pass token-based chunking per doc; metadata `source` + `chunk_index`; full_document recall returns correct count and order.

### Phase 3 — Full-doc path and optional image extraction (disk only)

| Item                      | Implementation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Full text per doc         | DocumentParser provides one full text per document; path documented in recall-and-ingest-pdf-facts.md §4.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| Optional image extraction | `extract_pdf_images()` (pymupdf) renders each PDF page to PNG; opt-in via `knowledge.ingest_extract_images`. Images are **saved to disk** (`.cache/omni-vector/images/{stem}/`). Ingest result includes **`image_paths`** (list of local paths). Paths are stored in **`.cache/omni-vector/image_manifests.json`** (source → paths). **full_document recall** returns **`image_paths`** for that source when present, so the LLM (or user) can **read images by path** (e.g. in Cursor, pass the path and the model can read the file). Images are not in the vector store as chunks; reading is by providing the path. |

### Phase 4 — Tests and docs

| Item        | Implementation                                                                                                                                                                               |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Rust tests  | omni-tokenizer: `test_chunk_text_*`, `test_tokenizer.rs` (token-boundary, overlap, chunk_index, no duplicates).                                                                              |
| Python test | `assets/skills/knowledge/tests/test_ingest_recall_full_document.py` — ingest with Rust chunker, then `knowledge.recall` `action=full_document` `source=...` returns correct count and order. |
| Docs        | Backlog entry **UltraRAG-Style Ingest (Complete Implementation)**; recall-and-ingest-pdf-facts.md; this milestone.                                                                           |

---

## Enhancements (beyond original plan)

| Enhancement                      | Description                                                                            |
| -------------------------------- | -------------------------------------------------------------------------------------- |
| full_document batching           | `full_document_batch_size`, `full_document_batch_index` to avoid token-limit overflow. |
| source_filter predicate pushdown | Rust `list_all_tools(table_name, source_filter)`; significant I/O reduction.           |
| Default batch_size=15            | Fewer full_document calls, lower overhead.                                             |

---

## LLM reading PDF-extracted images (by path)

PDF page images are not stored in the vector store. They are saved to disk and **paths are exposed** so the LLM can read them when given the path:

- **Ingest result**: After ingest with `knowledge.ingest_extract_images=true`, the result includes **`image_paths`** (list of absolute paths). You can pass any of these paths to the model (e.g. in Cursor, the model can read the image file at that path).
- **full_document recall**: When you call recall with `action=full_document` and `source=...` (e.g. the PDF filename or path), the response includes **`image_paths`** for that source when available (from `.cache/omni-vector/image_manifests.json`). Use those paths so the LLM can read the extracted page images.

So: **provide the path** (from ingest result or from recall’s `image_paths`) and the model can read the image. No vision embedding or image-in-vector-store required for this flow.

---

## Success criteria (met)

- Re-ingest of the same file does not create duplicate chunk rows for that source.
- Ingest uses Rust token-based chunking; full_document recall returns exactly one chunk per chunk_index for that source.
- Docs and backlog describe the pipeline; we do not add UltraRAG as a dependency.

---

## References

| Topic                   | Document                                                                                  |
| ----------------------- | ----------------------------------------------------------------------------------------- |
| Recall and ingest facts | [recall-and-ingest-pdf-facts.md](../explanation/recall-and-ingest-pdf-facts.md)           |
| Ingest logic            | `assets/skills/knowledge/scripts/graph.py`                                                |
| Rust delete-by-source   | `packages/rust/crates/omni-vector/src/ops/admin_impl.rs`                                  |
| Rust chunking           | `packages/rust/crates/omni-tokenizer`, `bindings/python/src/tokenizer.rs` (py_chunk_text) |
| Vector CRUD             | `packages/python/foundation/src/omni/foundation/services/vector/crud.py`                  |
| PDF images              | `packages/python/foundation/src/omni/rag/pdf_images.py` (extract_pdf_images)              |

# Recall and Ingest PDF: Facts and Improvements

> Clarifying: (1) Whether recall returns the **full document with no omission**; (2) Whether we capture **PDF images** and **fully use** UltraRAG / the PDF API.

---

## 1. Does recall return the full document with no omission?

**No.**

- Ingested documents are stored as **multiple chunks** (e.g. 31 for one paper) in `knowledge_chunks`.
- Standard **recall** is **similarity search**: it returns the **top-N chunks** most similar to the query, with a cap (`preview_limit` / `limit`). It does **not** return chunks in document order or guarantee all chunks of one document.
- So there **can be omission**, and there is no built-in “full linear document” read.

**Solution (implemented):** Use **full-document recall** so stored documents can be retrieved and read in full:

- In **knowledge.recall**, use **`action=full_document`** with **`source=`** (file path or identifier, e.g. `2602.12108.pdf` or the full path). The skill returns **all chunks** for that document, sorted by `chunk_index`, so the document can be reassembled and read completely.

---

## 2. Do we get PDF image content? Do we fully use UltraRAG / the PDF API?

**No.** We do not capture PDF image content in ingest, and we do not use UltraRAG’s PDF API in the ingest pipeline.

### 2.1 What “UltraRAG” vs “PDF parsing” mean in this repo

- **UltraRAG** (see `docs/explanation/ultrarag-gap-analysis.md`, `tracer/graphflow`): **execution tracing / pipeline** (UltraData, Memory, YAML pipeline, stream callbacks). It does **not** handle PDF parsing.
- **PDF parsing** is done by **RAG-Anything** (`raganything`, HKUDS/RAG-Anything): `DocumentParser` uses `BatchParser` (docling/mineru) and an optional **pdfminer** fast path.

So there is **no** “UltraRAG PDF API” used in ingest; that role is played by RAG-Anything.

### 2.2 What the ingest pipeline actually does (graph.py + document.py)

- **Step 1:** `ingest_document` calls `DocumentParser().parse(path, fast_path_for_pdf=pdf_fast_path)`.
- **`ingest_pdf_fast_path: true` (default):**
  - Uses **pdfminer** for **text-only** extraction. **No** figures or table structure; **no** image content.
- **`ingest_pdf_fast_path: false`:**
  - Uses **RAG-Anything BatchParser** (docling/mineru), which writes a **.md** file.
  - The code reads **one .md** as a single text block.
  - **`_clean_text()`** replaces all `![alt](data:image/...;base64,...)` with **`[Image Data Removed]`**, so image data is **discarded**.
- **Result:** In both paths, **image content is not retained or embedded**. Table text in the .md is kept.

### 2.3 Where the “full” PDF / multimodal API lives

- **`omni.rag.adapter.OmniRAGAdapter`** uses RAG-Anything’s **ImageModalProcessor**, **TableModalProcessor**, **EquationModalProcessor** (images, tables, equations).
- **`ingest_document`** (graph.py) only uses **`DocumentParser`**; it does **not** call **`OmniRAGAdapter.process_document()`**, so the **multimodal / image / table** pipeline is **not** used for ingest.

### 2.4 Summary (second question)

| Question                                  | Current state                                                                                                                   |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Do we get PDF image content?              | **No.** Either text-only (fast path) or images removed by `_clean_text`.                                                        |
| Do we use “UltraRAG” PDF API?             | **UltraRAG** in this repo is not a PDF API; PDF parsing is RAG-Anything. Ingest does **not** use RAG-Anything’s multimodal API. |
| Do we fully use the PDF/multimodal stack? | **No.** Image/Table/Equation processing exists in the adapter but is **not** used in the ingest pipeline.                       |

---

## 3. Implemented and recommended improvements

### 3.1 Full-document recall (implemented)

- **knowledge.recall** supports **`action=full_document`** with **`source=`** (path or doc identifier).
- The skill uses the store’s list capability, filters by **metadata.source**, sorts by **chunk_index**, **deduplicates by chunk_index** (keeps first occurrence per index so duplicate DB rows do not repeat chunks), and returns all chunks for that document so it can be **searched out and read in full** from the database.

### 3.2 Using PDF images and RAG-Anything multimodal API (recommended)

- **Option A:** In **ingest_document**, add a path (e.g. when `knowledge.ingest_multimodal_pdf: true`) that calls **`OmniRAGAdapter.process_document(path, multimodal=True)`** and ingests the resulting chunks (including image/table representations) into the vector store.
- **Option B:** When **fast_path_for_pdf=false**, keep **image blocks** (e.g. `type: "image"` or refs) instead of stripping them in `_clean_text`, and extend chunking/embedding to handle them (e.g. vision embeddings or caption text).
- Add settings (e.g. `knowledge.ingest_pdf_fast_path`, `knowledge.ingest_multimodal_pdf`) and document that fast path = text-only/speed, multimodal = RAG-Anything with images/tables.

### 3.3 Documentation and naming

- In docs, keep **UltraRAG** = execution tracing / pipeline; **RAG-Anything** = document parsing and multimodal (PDF, images, tables, equations). If a separate “UltraRAG PDF API” is introduced later, document it and wire it into ingest as needed.

---

---

## 4. Learning from OpenBMB/UltraRAG: full data extraction

The **OpenBMB/UltraRAG** repo ([GitHub](https://github.com/OpenBMB/UltraRAG)) implements a **corpus server** (`servers/corpus/src/corpus.py`) that shows a mature, pipeline-style approach to **complete document extraction**. We can align our ingest and recall with these ideas.

### 4.1 UltraRAG corpus pipeline (source: `servers/corpus`)

| Step             | Tool / behaviour                                                  | Purpose                                                                                                                                                                                                                                   |
| ---------------- | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Text corpus**  | `build_text_corpus(parse_file_path, text_corpus_save_path)`       | One row per file: `id`, `title`, `contents`. For PDF: **pymupdf** `pg.get_text("blocks")`, sort blocks by (y, x), then `reflow_paragraphs(clean_text(content))`.                                                                          |
| **Image corpus** | `build_image_corpus(parse_file_path, image_corpus_save_path)`     | **pymupdf** renders each page with `page.get_pixmap()`, saves as JPG; JSONL has `id`, `image_id`, `image_path`.                                                                                                                           |
| **MinerU path**  | `mineru_parse()` then `build_mineru_corpus()`                     | CLI `mineru -p <path> -o <dir>`; then read `{mineru_dir}/{stem}/auto/{stem}.md` for **full markdown** and `auto/images/` for extracted images; output **text + image** corpora.                                                           |
| **Chunking**     | `chunk_documents(raw_chunk_path, chunk_backend, chunk_size, ...)` | **chonkie** (TokenChunker / SentenceChunker / RecursiveChunker) + tiktoken; one **global chunk id** per chunk; each chunk has `doc_id`, `title`, `contents`. No duplicate chunk indices: chunks are built once from a single text corpus. |

So UltraRAG:

- **Separates** text extraction, image extraction, and chunking into clear steps.
- **Keeps full-doc text** (one `contents` per doc in text corpus) before chunking; chunking adds `id` (chunk index) and `doc_id`.
- **Supports both** quick PDF text (pymupdf) and **rich extraction** (MinerU → markdown + images).
- **Avoids duplicate chunks** by building chunks in one pass from a single corpus.

### 4.2 Why we don’t add UltraRAG as a dependency

- **UltraRAG as a Python dependency is heavy** and overlaps with what we already have: we implement equivalent flows **on our side** instead of pulling in the full stack.
- **We have Rust implementations** (e.g. **omni-tokenizer** with **tiktoken-rs** for tokenization; omni-vector for storage and list/dedup). We can **learn from UltraRAG’s design** (text corpus → chunk once → source + chunk_index) and **fully implement it here**: same pipeline ideas, our own code and dependencies.

So: **reference UltraRAG’s corpus design in docs**, implement **text extraction → single-pass chunking (e.g. token/sentence with tiktoken-rs) → write with source + chunk_index** and optional **image corpus** in our ingest path, without adding UltraRAG as a dependency.

### 4.3 Takeaways for our implementation

- **Recall:** We **deduplicate by (source, chunk_index)** (Rust-side in `list_all_tools`); full-document recall returns each chunk once, in order.
- **Ingest:** Align with UltraRAG’s flow **using our stack**:
  - **Text:** Full-doc extraction (pymupdf / RAG-Anything / MinerU) → one `contents` per doc, then **single-pass chunking** (e.g. with **omni-tokenizer / tiktoken-rs** for token-aware chunking), assign global chunk index and `doc_id`/`source`, write to DB. No duplicate chunk_index at source.
  - **Image:** Optionally mirror **build_image_corpus**: pymupdf (or existing parser) page → image, separate image corpus or multimodal chunks.
- **Chunk identity:** Store **source + chunk_index** in metadata; ingest does one chunking pass per document so we don’t create duplicate indices.

_This document reflects the current code and ingest/recall behaviour. Full-document recall uses Rust-side dedup; we implement UltraRAG-style pipeline with our own Rust/Python stack (tiktoken-rs, omni-tokenizer, etc.) without adding UltraRAG as a dependency._

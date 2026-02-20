# Knowledge Pytest Memory Deep Dive

> Root-cause analysis for high RSS (~1.5 GB) of the pytest worker when running
> `uv run pytest assets/skills/knowledge/tests/ -v -q -n 1`.

---

## 1. Executive Summary

| Observation                                                  | Cause                                                                                                                                                                                       |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **~1.5 GB RSS** on the pytest worker (PID 34304 in your run) | Single worker loads full `omni.rag` + optional Polars + foundation + skill scripts; session mocks avoid real vector/embedding but do not reduce import cost.                                |
| **High baseline** before any test runs                       | Conftest imports `omni.test_kit.fixtures.rag`, which pulls in `omni.rag.config`; **any** import from `omni.rag.*` triggers the **entire** `omni.rag` package `__init__.py` (eager imports). |
| **~100–140 MB** from “just” RAG config                       | `omni.rag` package eagerly imports analyzer, chunking, dual\*core, entities, graph, multimodal, retrieval, link_graph\*, etc., so one config import loads 30+ submodules.                   |

**Main levers**: (1) Eager `omni.rag` package init, (2) optional Polars in analyzer, (3) full skill script load when using `skill_tester`, (4) no process isolation between tests (single worker).

---

## 2. Call and Import Chain

### 2.1 Process Layout

```
PID 34292  zsh     (runner: pytest ... | tail -50)
  └─ 34299  uv
  └─ 34300  tail
  └─ 34301  pytest (main)
       └─ 34304  python (worker: runs tests)  ← ~1.5 GB RSS
```

The heavy process is the **pytest worker** (34304), not the shell (34292).

### 2.2 What Gets Loaded (Order)

1. **Root conftest** (project-wide)
   - Memory protection (RSS cap, abort on delta).
   - No heavy imports.

2. **Knowledge conftest** (`assets/skills/knowledge/tests/conftest.py`)
   - `SKILLS_DIR` → `omni.foundation.config.skills`.
   - `from omni.test_kit.fixtures.rag import mock_knowledge_graph_store, mock_llm_*, ...`
   - That triggers `omni.test_kit.fixtures.rag`, which does:
     - `from omni.rag.config import RAGConfig, KnowledgeGraphConfig, DocumentParsingConfig`.
   - In Python, **any** `from omni.rag.<submodule> import ...` runs `omni.rag.__init__.py` first.

- So **full `omni.rag`** is loaded: config, chunking, entities, graph, multimodal, link_graph_navigator, link_graph (backend/factory/policy), dual_core, unified_knowledge, **analyzer**, retrieval, pdf_images (30+ submodules).
- **Session-scoped fixture** `_mock_heavy_services` then patches:
  - `omni.foundation.services.vector.get_vector_store`
  - `omni.foundation.services.embedding.get_embedding_service`
- So real LanceDB and sentence-transformers are never used, but **the import graph has already been executed** (vector, embedding, omni.rag, etc.).

3. **Tests that use `skill_tester`** (e.g. `test_knowledge_modular.py`)
   - `skill_tester` uses `load_skill_scripts("knowledge", scripts_dir)`.
   - That **exec_module**’s every `*.py` in `assets/skills/knowledge/scripts/`: recall, graph, paper_workflow, search (and search’s submodules: keyword, link_graph, vector, hybrid).
   - `recall` does `from omni.foundation import get_vector_store` → foundation services.vector (already patched).
   - `search/link_graph.py` uses `from omni.rag.link_graph import get_link_graph_backend, link_graph_hits_to_search_results`.
   - `search/hybrid.py` uses `plan_link_graph_retrieval` and vector fallback through `search/vector.py` + `link_graph.search_results`.
   - No `SkillManager` import in this path, so `omni.core.services.skill_manager` (which does top-level `from omni_core_rs import PyVectorStore`) is not loaded by default.

4. **Tests that import skill scripts directly**
   - `test_recall_filter.py`: `import recall`
   - `test_search_completeness.py`: `from search import run_search, search_keyword, ...`
   - `test_graph_search.py`: `from graph import search_graph`
   - These again pull in foundation and, for search, the full search package (link_graph, hybrid, vector).

5. **Lazy `omni_core_rs`**
   - Not loaded by skill_loader or by the conftest.
   - Loaded only if some **code path** runs that does `from omni_core_rs import ...` (e.g. inside `omni.rag.graph`, `omni.rag.dual_core`, or if a test/fixture ever imports `SkillManager`). With `mock_knowledge_graph_store` patching `KnowledgeGraphStore.__init__`, many graph tests never touch the Rust backend.
   - When loaded, the Rust extension + tiktoken/data can add on the order of tens to low hundreds of MB.

### 2.3 Measured Baseline (Minimal Script)

```text
After interpreter:              ~15 MB
After foundation.config.skills:  ~25 MB
After test_kit.fixtures.rag:     ~139 MB   ← omni.rag full load
After link_graph adapters load:   ~139 MB   (no extra; omni.rag already loaded)
POLARS_AVAILABLE: True → same    ~139 MB   (Polars already loaded in analyzer)
```

So **~110–120 MB** is attributable to the **full `omni.rag`** load (including analyzer, retrieval, dual\*core, graph, link_graph\*, etc.) triggered by the first `omni.rag.config` import from the RAG fixtures.

---

## 3. Memory Breakdown (Pytest Worker)

| Source                                       | Est. RSS        | Notes                                                                      |
| -------------------------------------------- | --------------- | -------------------------------------------------------------------------- |
| Python + foundation (config, dirs, logging)  | ~25 MB          | Before any RAG.                                                            |
| **Full omni.rag** (eager init)               | **~100–140 MB** | Single import from `omni.rag.config` in fixtures.rag pulls entire package. |
| Polars (in analyzer)                         | ~50–200 MB      | If installed; analyzer imports it at package init.                         |
| omni.foundation.services (vector, embedding) | ~10–30 MB       | Module code + mocks; no real store/model.                                  |
| Skill scripts (recall, graph, search)        | ~10–30 MB       | Loaded when tests use skill_tester or direct script imports.               |
| omni_core_rs (if any path loads it)          | ~50–150 MB      | Lazy; only when graph/dual_core or SkillManager is used.                   |
| Test data + tracemalloc + fragmentation      | Variable        | Per-test growth; cap/abort in root conftest.                               |

Cumulative baseline is already **~200–400 MB** before running a single test; under load (Polars + optional omni_core_rs + many tests in one process), **~1–1.5 GB** is plausible.

---

## 4. Root Causes

### 4.1 Eager `omni.rag` Package Init

- **Location**: `packages/python/foundation/src/omni/rag/__init__.py`
- **Behavior**: Top-level `from .config import ...`, `from .analyzer import ...`, `from .retrieval import ...`, etc. So **any** first import of an `omni.rag` submodule runs the whole package.
- **Impact**: Tests that only need `RAGConfig` or a small RAG surface still pay for analyzer (Polars), retrieval (LanceDB backend references), graph, dual\*core, link_graph\*, multimodal, etc.

### 4.2 RAG Fixtures Depend on `omni.rag.config`

- **Location**: `packages/python/test-kit/src/omni/test_kit/fixtures/rag.py`
- **Behavior**: `from omni.rag.config import RAGConfig, KnowledgeGraphConfig, DocumentParsingConfig` and fixtures that use them.
- **Impact**: As soon as knowledge conftest does `from omni.test_kit.fixtures.rag import ...`, the full `omni.rag` package is loaded for the whole session.

### 4.3 Session Mocks Do Not Reduce Import Cost

- **Location**: `assets/skills/knowledge/tests/conftest.py` — `_mock_heavy_services`
- **Behavior**: Patches `get_vector_store` and `get_embedding_service` so no real LanceDB or embedding model is created.
- **Impact**: Prevents **runtime** memory from vector store and sentence-transformers, but **all modules that reference them are still imported** (foundation.services.vector, omni.rag.retrieval, etc.), so the import-time cost remains.

### 4.4 Single Worker (`-n 1`)

- All knowledge tests run in one process; baseline (omni.rag + Polars + foundation) is paid once, then per-test growth and fragmentation add up in the same process.

### 4.5 Optional Polars in Analyzer

- **Location**: `packages/python/foundation/src/omni/rag/analyzer.py`
- **Behavior**: At package init, `omni.rag` imports analyzer, which does `try: import polars as pl; POLARS_AVAILABLE = True`.
- **Impact**: If Polars is installed, it is loaded for every test run that touches `omni.rag`, even when no test uses the analyzer.

---

## 5. Recommendations

### 5.1 Short-Term (Configuration / Test Layout)

1. **Run with `-s`** when debugging memory so conftest’s tracemalloc logs (RSS before/after, top allocations when delta &gt; threshold) are visible.
2. **Lower threshold** for dumps:  
   `KNOWLEDGE_TEST_MEMORY_THRESHOLD_MB=10 pytest assets/skills/knowledge/tests/ -v -s`
3. **Try `-n 2`** (or a small N): Same total memory across workers but lower peak per process if tests are spread; verify no shared-state issues.
4. **Optional**: Use a separate venv or env without Polars for knowledge tests if analyzer is not under test, to avoid Polars load.

### 5.2 Medium-Term (Code)

1. **Lazy-load `omni.rag` submodules**
   - In `omni.rag.__init__.py`, expose submodules via `__getattr__` (similar to `omni.foundation`) so that `from omni.rag.config import RAGConfig` does **not** execute `analyzer`, `retrieval`, `graph`, etc.
   - Only the submodule actually requested (e.g. `config`) is loaded. This reduces baseline RSS for any entry point that only needs config.

2. **Thin RAG fixtures**
   - If possible, have a minimal test path that does not import from `omni.rag.config` (e.g. use a small inline config or a stub) so that tests that do not need full RAG do not pull in the package at all.
   - Or move “heavy” fixtures behind a separate plugin/conftest that is only used by tests that need full RAG.

3. **Defer Polars in analyzer**
   - In analyzer, do `import polars` only inside the functions that need it (e.g. `create_entities_dataframe` / `create_relations_dataframe`), not at module top-level, so that merely importing `omni.rag` does not load Polars.

### 5.3 Long-Term (Architecture)

1. **Split test suites**
   - “Light” knowledge tests (e.g. only config, or only keyword search) that do not load full omni.rag or skill scripts.
   - “Heavy” knowledge tests (skill_tester, recall, hybrid, graph) that accept the full stack and higher RSS.
   - Run light suite by default; heavy suite in CI or when explicitly requested.

2. **Document expected RSS**
   - In `assets/skills/knowledge/tests/conftest.py` or in this doc, state that a single worker with full omni.rag + Polars can reasonably use **~300–600 MB** baseline and up to **~1–1.5 GB** under load, and that session mocks avoid further growth from real vector/embedding.

---

## 6. References

- **Production recall memory**: `docs/explanation/knowledge-recall-memory-analysis.md` (MCP/embedding/vector cache, not pytest).
- **Knowledge conftest**: `assets/skills/knowledge/tests/conftest.py` (session mocks, tracemalloc, SKILLS_DIR).
- **RAG fixtures**: `packages/python/test-kit/src/omni/test_kit/fixtures/rag.py` (RAGConfig, mock graph, chunkers).
- **omni.rag package**: `packages/python/foundation/src/omni/rag/__init__.py` (eager imports).
- **Root conftest**: project root `conftest.py` (memory cap, abort delta).

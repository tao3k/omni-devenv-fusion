# Guide: LinkGraph Precision Code Adaptation (2026)

> **Goal:** Document the exact code changes required to align the `link_graph` package with HippoRAG, GRAG, and HMAS research.
> **Reference Papers:** [HippoRAG (2025)](../../.data/research/papers/HippoRAG_2405.14831.txt), [GRAG (2025)](../../.data/research/papers/GRAG_2405.16506.txt).

---

## 1. Schema Extensions (`packages/shared/schemas/`)

### 1.1 `xiuxian_wendao.link_graph.saliency.v1.schema.json`

**Target Change:** Add support for high-fidelity cognitive metadata.

- **Add Field:** `source_claims` (array[string]) - _Basis: GRAG Narrative Context._
- **Add Field:** `triples` (array[array[string]]) - _Basis: HippoRAG OpenIE Indexing._
- **Add Field:** `saliency` (number 0-10) - _Basis: HippoRAG PPR Start Distribution._

---

## 2. Model Adaptations (`packages/python/foundation/src/omni/rag/link_graph/models.py`)

### 2.1 `LinkGraphHit` Data Class

**Proposed Refinement:**

```python
@dataclass(frozen=True)
class LinkGraphHit:
    # Existing fields...
    source_claims: list[str] = field(default_factory=list) # For GRAG
    triples: list[list[str]] = field(default_factory=list) # For HippoRAG
    saliency: float | None = None                         # For PPR weighting
```

---

## 3. Algorithm Refinement (`packages/python/foundation/src/omni/rag/link_graph/policy.py`)

### 3.1 Dynamic Damping Logic (HippoRAG Alignment)

**Target:** Replace hardcoded `alpha` (damping) with a query-aware controller.
**Proposed Algorithm:**

- **Baseline:** $d = 0.5$ (Paper p.4 recommendation for ZK graphs).
- **Rule A (Focus):** If `confidence > 0.8`, increase $d$ to $0.7$ (Focus on the specific node).
- **Rule B (Explore):** If `query_length > 100` or `confidence < 0.4`, decrease $d$ to $0.3$ (Deep topological exploration).

### 3.2 Saliency-Weighted Confidence

**Proposed Formula Change:**
Include **"Distribution Parity"** in the confidence score. If scores are too evenly spread, confidence in a specific structural path is lowered.

---

## 4. Narrative Topology (`packages/python/foundation/src/omni/rag/link_graph/narrator.py`)

**New Component Requirement:**
Implement a `SubGraphNarrator` that:

1. Iterates through `LinkGraphHit.source_claims`.
2. Assembles a "Hierarchical Narrative" hard-prompt.
3. **Format:** `[Concept A] links to [Concept B] because of [Claim X]`.
   _Purpose: Prevents LLM reasoning drift during long-context retrieval (GRAG Core Theory)._

---

## 5. Storage Architecture: Dual-Drive Memory Network

This project implements a hybrid storage strategy to balance semantic precision (LanceDB) with low-latency associative reasoning (Valkey).

### 5.1 LanceDB (Cortex Trigger)

- **Role:** High-cost semantic entry point lookup.
- **Data:** `[note_id, semantic_anchor_vector]`.
- **Constraint:** Do NOT vectorize full body. Only vectorize 1-sentence summaries.

### 5.2 Valkey (Hippocampal Engine)

- **Role:** Low-cost structural walk and weight updates.
- **Key Naming Convention:**
  | Domain | Key Template | Type | Usage |
  | :--- | :--- | :--- | :--- |
  | **KG Nodes** | `xiuxian_wendao:link_graph:saliency:{id}` | String(JSON) | Stores saliency state (`activation_count`, `decay_rate`, `current_saliency`) |
  | **KG Edges** | `xiuxian_wendao:link_graph:index:kg:edge:out:{id}` | **ZSET** | Stores linked nodes scored by current target saliency |
  | **Blackboard** | `xiuxian_wendao:hmas:bb:{req_id}` | Hash | TTL-guarded shared working memory |
  | **Audit Stream**| `xiuxian_wendao:hmas:trace` | **Stream** | Immutable digital thread log |

---

## 6. Implementation: Self-Evolving Saliency (Valkey Logic)

### 6.1 Manager System Prompt (Strategy Layer)

- **Role:** Supervisor.
- **Instruction:** "Post tasks to the blackboard using [TASK] tags. You must validate the [DIGITAL THREAD] JSON of workers against the original requirement."

### 6.2 Worker System Prompt (Tactical Layer)

- **Role:** Executor.
- **Instruction:** "Read [TASK] from the blackboard. Output observations in [EVIDENCE] and a final JSON [DIGITAL THREAD] mapping your conclusion to source nodes."

---

## 7. Implementation Roadmap & Audit Tags

Each code change must be tagged with `[ADAPT-2026-CODE]` in commit messages for traceability.

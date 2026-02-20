# Template: Knowledge Ingestion & Zettelkasten Entry

> **Basis:** _HippoRAG Schema-less KG Integration (2025)_.
> **Version:** 2026.Q1

## 1. Overview

Use this template when adding new "Stable Knowledge" to the LinkGraph or project docs. This structure is optimized for **PPR (Personalized PageRank)** ranking.

---

## [TITLE] <!-- CONCEPT: unique_id -->

### Metadata

- **ID:** `note-unique-slug`
- **Type:** (MOC / Concept / Implementation / Archive)
- **Saliency_Base:** 5.0 (Initial structural weight)
- **Decay_Rate:** 0.01 (Temporal遗忘率 \lambda)
- **Activation_Count:** 0 (Refreshed by Agentic activation \gamma)
- **Last_Accessed:** "YYYY-MM-DD" (Used for \Delta t calculation)
- **Current_Saliency:** 5.0 (Calculated output \phi)

### 0. Dynamic Saliency Formula (GraphMem Alignment)

The effective saliency $\phi$ at query time is computed as:
$$\phi = \text{clamp}(S_{base} \cdot e^{-\lambda \Delta t} + \eta \cdot \ln(1 + \gamma), 1.0, 10.0)$$

- $\Delta t$: Days since `Last_Accessed`.
- $\gamma$: `Activation_Count`.
- $\eta$: Activation learning rate (Default: 0.5).

### 1. Abstract (For Librarian Vector Seeds)

_Provide a 2-3 sentence summary. Must contain at least 3 Named Entities identified in the HippoRAG Ingestion Phase._

### 2. Core Principles & Claims

_List atomic claims. Each claim will be extracted as a node in the GRAG Hierarchical View._

### 3. Structural Connections (HippoRAG Triples)

- **Triples:**
  - [Subject] --(Relation)--> [Object]
  - [Subject] --(Relation)--> [Object]
- **Parent:** [[link_to_higher_hierarchy]] (Community Level)

### 4. Implementation Details

_Code snippets, math, or specific configurations._

```rust
// Example code relevant to this concept
```

### 5. Audit Trail (Internal)

- **Source:** (URL / Conversation / Research Paper)
- **Verification:** (Verified by 3-in-1 Gate / Peer Review)
- **Last Integrity Check:** YYYY-MM-DD

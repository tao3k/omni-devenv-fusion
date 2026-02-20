# Standard: LLM Reading Guide (Project Omni)

> **Basis:** _GRAG (2025)_, _HippoRAG (2025)_, and _llms.txt_ proposal.
> **Version:** 2026.Q1

## 1. Purpose

This guide defines how this project’s documentation and codebase should be structured to maximize "Machine Comprehension Efficiency." It ensures that external LLMs (via RAG or direct context) can navigate the **LinkGraph** and **Librarian** systems with zero ambiguity.

## 2. Structural Requirements

### 2.1 The Two-View Principle (GRAG 2025)

Every complex architectural component must be documented with two synchronized views:

1.  **Text View:** A hierarchical Markdown description (H1-H3) focusing on "What" and "Why."
2.  **Graph View (Hierarchical Narrative):** A "Hard Prompt" ($D_g$) that narrates topological connections.
    - **Mandatory Requirement:** The description must preserve "How connections are narrated." Use a nested structure where each relationship is paired with its atomic claim (source sentence).
    - **Format:** `[Entity A] --(Relation based on Claim X)--> [Entity B]`.

### 2.2 Semantic Anchors & HippoRAG Ingestion

- **Hyperparameter Lockdown (Audit Baseline):**
  - **PPR Damping Factor ($d$):** Fixed at **0.5** for optimal exploration-restart balance in Zettelkasten graphs.
  - **Synonymy Threshold ($\tau$):** Fixed at **0.8** for cosine similarity between entity representations.
- **Global Index (Hippocampus):** `/docs/index.md` serves as the primary seed source.

### 2.3 Self-Containment (Chunking Optimization)

- Each documentation file should be "RAG-ready."
- **Rule:** A sub-section (H2/H3) must contain all context needed to understand its logic, including references to its primary `TOOL_CONTRACT`.

## 3. Directory Navigation for LLMs

- `/docs/index.md`: The "Hippocampal Index." Serves as the global seed for PPR-based retrieval.
- `llms.txt`: A plain-text index at the root providing a concise map of high-signal files for context injection.

## 4. Code Documentation

- **Standard:** Use Google-style docstrings.
- **Traceability:** Every major function must include a reference to its **System Card** requirement (e.g., `[Ref: REQ-MEM-01]`).

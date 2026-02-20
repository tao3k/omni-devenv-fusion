# MemRL vs Omni-Dev-Fusion: Research Analysis

> **Paper**: [MemRL: Self-Evolving Agents via Runtime Reinforcement Learning on Episodic Memory](https://arxiv.org/abs/2601.03192) (arXiv:2601.03192)  
> **Purpose**: Extract learning points, advantages, and adoptable ideas for the current project.

---

## 1. Paper Summary (MemRL)

**Core claim**: Agents can self-evolve at runtime by doing reinforcement learning **on episodic memory**, without updating model weights.

| Aspect        | MemRL                                                                                                                           |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Problem**   | Fine-tuning is expensive and causes catastrophic forgetting; passive semantic retrieval often returns noise.                    |
| **Approach**  | Non-parametric: **decouple stable reasoning from plastic memory**.                                                              |
| **Memory**    | Episodic memory (past trajectories / experiences).                                                                              |
| **Retrieval** | **Two-Phase Retrieval**: filter noise and identify high-utility strategies using **environmental feedback** (reward signal).    |
| **Update**    | No weight updates; only memory content evolves.                                                                                 |
| **Result**    | Addresses stability–plasticity dilemma; continuous improvement at runtime on HLE, BigCodeBench, ALFWorld, Lifelong Agent Bench. |

**Takeaways**: (1) Episodic memory + RL-style feedback beats “store everything + semantic search”. (2) Two-phase retrieval (recall then utility filter) reduces noise. (3) Keeping reasoning fixed and only evolving memory avoids forgetting and keeps deployment simple.

---

## 2. Our Project’s Current Memory & Knowledge

| Component          | Role                                                | Implementation                                                                                               |
| ------------------ | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Hippocampus**    | Long-term memory for “I remember doing that before” | LanceDB + LLM embedding (1024-dim). **Selective storage**: multi-step success, retry→success; not every run. |
| **Skill Memory**   | “I know how to do” (protocols, metadata)            | `skill_index.json` + SKILL.md, core vs active skills, require_refs.                                          |
| **Knowledge**      | “I know what that is” (entities, docs)              | Ingest → chunk → entity/relation extraction → graph + vector store; recall/search (hybrid).                  |
| **Memory Mesh**    | Episodic memory for self-learning                   | Memory Mesh doc; table (Skills / Knowledge / Memory) + AdaptiveLoader + Agent Runtime.                       |
| **Project Memory** | ADR-style decisions, tasks, context                 | ProjectMemory, LanceDB, decisions/tasks/context.                                                             |

**Trinity**: Skills + Knowledge + Memory; single entry point `@omni("skill.command")`, MCP, skill-centric.

---

## 3. Learning Points (What We Can Learn from MemRL)

1. **Explicit “utility” over raw similarity**  
   MemRL uses **environmental feedback** (e.g. task success) to select which episodes are high-utility. We store “valuable learnings” in Hippocampus but do **not** currently score or filter by outcome (e.g. “this pattern led to success”).  
   **Idea**: Add an optional **utility/reward signal** when saving to Hippocampus (e.g. task success, user confirm) and use it in retrieval (e.g. two-phase: semantic recall → rank by utility).

2. **Two-phase retrieval to cut noise**  
   MemRL first retrieves candidates, then filters by utility. We already have hybrid search (LinkGraph + vector) and graph; we could add a **second phase** for memory recall: “among recalled episodes, prefer those that led to success or were explicitly endorsed.”

3. **Stable reasoning vs plastic memory**  
   We already separate: **reasoning** = LLM + skills + router (no persistent learning in weights); **plastic part** = Hippocampus + Knowledge graph + Project Memory. This aligns with MemRL’s split. We can document this explicitly as “stable reasoning, plastic memory” in architecture docs.

4. **Episodic structure**  
   MemRL stores **episodes** (trajectories with state/action/outcome). Hippocampus stores “learnings” as semantic snippets. We could evolve toward **episode-like units** (e.g. “task type + steps + outcome”) for better reuse and utility scoring.

---

## 4. Advantages We Already Have

| Advantage                | Description                                                                                                                            |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Selective storage**    | Hippocampus only stores valuable learnings (multi-step, retry→success), not every run — similar in spirit to “high-utility” selection. |
| **Trinity separation**   | Skills (how) / Knowledge (what) / Memory (remember doing) is a clear separation of roles and data sources.                             |
| **No weight updates**    | We do not fine-tune the LLM; all learning is in memory/graph — same non-parametric philosophy as MemRL.                                |
| **Structured knowledge** | Entity/relation graph + vector store gives both semantic and relational recall; MemRL focuses on episodic utility.                     |
| **Single entry point**   | `@omni("skill.command")` + MCP keeps the interface stable while we add or change memory/knowledge backends.                            |

---

## 5. Concrete Suggestions for the Project

1. **Document “stable reasoning, plastic memory”** in `docs/human/architecture/memory-mesh.md` or hippocampus: reasoning (LLM + skills) is fixed at deploy time; only memory/knowledge content evolves.
2. **Optional utility tag when saving to Hippocampus**: e.g. `success=True/False` or `user_endorsed=True`; later use in retrieval (e.g. boost or filter by utility).
3. **Two-phase memory recall** (backlog candidate): phase 1 = semantic/vector recall; phase 2 = rank or filter by utility if the field exists.
4. **Keep current ingest pipeline** (PDF → chunks → entities/relations → graph + vectors): it already gives rich, queryable knowledge; MemRL does not replace this but suggests we can add “utility” for episodic memory specifically.

---

## 6. Summary

| Dimension    | MemRL                               | Omni-Dev-Fusion                                   |
| ------------ | ----------------------------------- | ------------------------------------------------- |
| Memory type  | Episodic (trajectories, outcomes)   | Semantic learnings + knowledge graph + ADR        |
| Retrieval    | Two-phase (recall + utility filter) | Hybrid (LinkGraph + vector); no utility phase yet |
| Feedback     | Environmental (reward)              | Implicit (we only store “valuable” runs)          |
| Reasoning    | Frozen                              | Frozen (no fine-tuning)                           |
| Plastic part | Episodic memory content             | Hippocampus + Knowledge + Project Memory          |

**Bottom line**: We already follow “non-parametric, stable reasoning, plastic memory.” The main adoptable idea is **explicit utility feedback and two-phase retrieval** for episodic memory (Hippocampus), to better select “which past experience to reuse” and reduce noise.

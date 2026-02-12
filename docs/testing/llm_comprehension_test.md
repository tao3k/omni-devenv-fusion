# LLM Comprehension Test: Omega Architecture

This document contains a set of questions and expected answers to verify if an LLM (after reading the documentation in `docs/llm/` and `docs/human/architecture/`) has a correct understanding of the Omni-Dev-Fusion system.

## Test Case 1: Core Metaphors

**Question:** What are the five primary systems in the Omega Architecture and what are their respective roles?

**Expected Answer:**

1. **Cortex**: Scheduling, task decomposition, and mission planning.
2. **Cerebellum**: Navigation, semantic scanning (AST), and codebase understanding.
3. **Hippocampus**: Long-term episodic memory, recalling past experiences (traces).
4. **Homeostasis**: Isolated execution, git branch management, and system stability.
5. **Evolution**: Self-learning, skill crystallization (Fast/Slow paths).

---

## Test Case 2: Knowledge Hierarchy

**Question:** If you need to find out the coding standard for this project, in what order should you search for information?

**Expected Answer:**

1. **Official Docs** (via `knowledge.*` or `cerebellum.scan_codebase`).
2. **Past Experiences** (via `hippocampus.recall_experience`).
3. **Raw Code** (last resort).

---

## Test Case 3: Memory & Learning

**Question:** What is the difference between the "Fast Path" and "Slow Path" in the Evolution system?

**Expected Answer:**

- **Fast Path**: Immediate learning and application of user rules, preferences, or corrections (stored in Hippocampus).
- **Slow Path**: Gradual crystallization of complex, successful workflows into permanent, optimized Skills (stored in `harvested/` directory).

---

## Test Case 4: Software Layering

**Question:** What is the relationship between the "Omega Architecture" and the "Trinity System Layers"?

**Expected Answer:**
The **Omega Architecture** defines the _functional/cognitive_ roles of the agent (Persona), while the **Trinity System Layers** define the _software_ structure (Foundation, Core, MCP-Server, Agent). The Omega systems operate on top of these software layers (e.g., Cortex runs in the Agent layer, Kernel in the Core layer).

---

## Test Case 5: Isolated Execution

**Question:** How does the system ensure that a dangerous shell command doesn't destroy the main codebase?

**Expected Answer:**
Through **Homeostasis**, which uses git branch isolation (every task runs in its own branch) and potentially **OmniCell** (sandboxed execution). The **Immune System** (Audit) also checks for conflicts and integrity before any merge.

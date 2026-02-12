# Omega Architecture (Biological Agent Model)

> **Status**: Active (Current Core Architecture)
> **Version**: v3.0 | 2026-02-09
> **Related**: Omni Loop, Trinity Architecture (Legacy)

## Overview

The **Omega Architecture** (Project Omega) is the highest-level architectural framework for Omni-Dev-Fusion. It uses biological metaphors to define the functional systems of an autonomous agent, moving beyond the static role-based Trinity v1.0.

## Core Functional Systems

| System            | Role                           | Metaphor               | Implementation                       |
| :---------------- | :----------------------------- | :--------------------- | :----------------------------------- |
| **Cortex**        | Scheduling & Task Decompostion | The Thinking Brain     | `omni.agent.core.cortex`             |
| **Homeostasis**   | Isolation & Stability          | The Internal Balance   | `omni.agent.core.cortex.homeostasis` |
| **Cerebellum**    | Navigation & Semantic Scanning | The Motor Coordination | `omni.agent.core.cerebellum`         |
| **Hippocampus**   | Long-term Memory & Recall      | The Memory Center      | `omni.agent.core.memory.hippocampus` |
| **Immune System** | Conflict Detection & Audit     | The Body's Defense     | `omni.agent.core.cortex.immune`      |
| **Evolution**     | Skill Crystallization          | Adaptation & Learning  | `omni.agent.core.evolution`          |

## System Details

### 1. Cortex (Scheduling)

The Cortex is responsible for high-level reasoning, mission planning, and task decomposition.

- **TaskDecomposer**: Breaks down a complex goal into a Parallel Directed Acyclic Graph (DAG) of tasks.
- **CortexOrchestrator**: Manages the execution flow of the task graph.

### 2. Homeostasis (Isolation)

Ensures the agent's actions are isolated and do not compromise system stability until verified.

- **Git Branch Isolation**: Every task runs in its own ephemeral git branch.
- **OmniCell**: Sandboxed execution environment for dangerous operations.

### 3. Cerebellum (Navigation)

Provides semantic understanding of the codebase and environment.

- **AST Scanning**: Fast, non-LLM semantic analysis of code structures.
- **Cerebellum Router**: Directs requests based on semantic signatures.

### 4. Hippocampus (Memory)

Manages long-term episodic memory (experiences).

- **Recall**: Searches for past successful (or failed) execution traces to guide current reasoning.
- **Commit**: Stores successful workflows as "Experiences" for future recall.

### 5. Immune System (Audit)

Detects conflicts and ensures semantic integrity during branch merges.

- **ConflictDetector**: Identifies overlapping changes in parallel tasks.
- **Semantic Audit**: Verifies that the codebase remains functional and idiomatic after changes.

### 6. Evolution (Learning)

The self-improvement loop of the agent.

- **Skill Crystallizer**: Converts repetitive successful workflows into permanent, optimized Skills.
- **Fast/Slow Path**:
  - _Fast Path_: Immediate learning of rules/preferences.
  - _Slow Path_: Gradual crystallization of procedural skills.

## Relationship with System Layering

The **Omega Architecture** is the _functional_ layer of the agent. It operates on top of the **Trinity System Layers**:

```
┌─────────────────────────────────────────────────────────────┐
│                 Omega Architecture (Agent Roles)            │
│  Cortex ↔ Cerebellum ↔ Hippocampus ↔ Homeostasis ↔ Evolution │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                 Trinity System Layers (Software)            │
│  L4: Agent (OmegaRunner, OmniLoop)                          │
│  L3: MCP-Server (Transport)                                 │
│  L2: Core (Kernel, Router, Skills)                          │
│  L1: Foundation (Serialization, I/O)                        │
└─────────────────────────────────────────────────────────────┘
```

For more details on the software structure, see [System Layering Architecture](../../explanation/system-layering.md).

## Implementation Map

- **OmegaRunner**: `packages/python/agent/src/omni/agent/core/omni/omega.py`
- **Cortex**: `packages/python/agent/src/omni/agent/core/cortex/`
- **Hippocampus**: `packages/python/agent/src/omni/agent/core/memory/hippocampus.py`
- **Evolution**: `packages/python/agent/src/omni/agent/core/evolution/`
- **Homeostasis**: `packages/python/agent/src/omni/agent/core/cortex/homeostasis.py`

## Related Documentation

- [Omni Loop](omni-loop.md) (CCA Runtime)
- [Knowledge Matrix](knowledge-matrix.md) (RAG System)
- [Skill Standard](skill-standard.md) (OSS 2.0)

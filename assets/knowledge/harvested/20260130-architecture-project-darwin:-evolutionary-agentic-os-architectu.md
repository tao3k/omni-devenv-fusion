# Project Darwin: Evolutionary Agentic OS Architecture

> **Category**: ARCHITECTURE | **Date**: 2026-01-30

# Project Darwin: The Evolutionary Agentic OS

## 1. Vision

Transform `omni-dev-fusion` into a self-evolving Agentic Operating System by integrating state-of-the-art research from AIOS, OS-Copilot, and GEA.

## 2. Theoretical Pillars

### 2.1 Kernel Layer: AIOS (LLM Agent Operating System)

- **Core Concept**: Define the LLM as the OS **CPU (Brain)**, and encapsulate traditional OS resources (files, processes, network) into a **Hypervisor/Abstraction Layer (HAL)**.
- **Omni Implementation**: `OmniCell` (Nushell/Rust Bridge) serves as the Micro-Kernel, isolating System Calls and providing structured resource access.
- **Evolution Path**: Implement **Context Scheduling**. Just as an OS schedules CPU cycles, the Kernel must schedule the LLM's Context Window, pruning irrelevant information to maximize cognitive density.

### 2.2 Evolutionary Layer: OS-Copilot (FRIDAY Agent)

- **Core Concept**: **Self-Directed Learning**. The agent generates its own curriculum to learn unfamiliar software/APIs and consolidates successful operations into reusable tools.
- **Omni Implementation**: **Skill Crystallization**. When the `Universal Solver` solves a novel problem (e.g., "batch convert webp to png"), it shouldn't just finish; it should synthesize a new `Python Skill` and persist it to `assets/skills/learned/`.

### 2.3 Architecture Layer: GEA (Generalist-Expert Architecture)

- **Core Concept**: **Mixture of Experts (MoE)** for Agents.
  - **Generalist**: Handles routing, planning, and long-tail/unknown tasks (ReAct loop).
  - **Expert**: Highly optimized atomic capabilities (Git, Research, Testing) for high-frequency tasks.
- **Omni Mapping**:
  - **Router**: The Manager/Dispatcher.
  - **Universal Solver**: The Generalist (Adaptive).
  - **Existing Skills**: The Experts (Deterministic/Optimized).

## 3. Implementation Roadmap

### Phase 1: Cognitive Kernel (Perception)

- **Status**: _In Progress (OmniCell)_
- **Goal**: Upgrade `OmniCell` from a "blind executor" to a "semantic filter".
- **Key Features**:
  - **Smart Query**: `query_structured(source, filter)` - Query the OS like a database rather than dumping raw text.
  - **Context Pruning**: Rust-based token counting and semantic truncation for CLI outputs (e.g., `ls` on large dirs).

### Phase 2: The Adaptive Generalist (Resilience)

- **Status**: _Design Phase_
- **Goal**: Create a fallback execution node that ensures the agent never hits a dead end.
- **Key Features**:
  - **Universal Solver Node**: A LangGraph node activated when `Router` returns no specific skill.
  - **Dynamic Plan Generation**: LLM writes ephemeral Nushell scripts based on real-time `sys_ops` feedback.
  - **Self-Correction Loop**: Execute -> Catch Stderr -> Refine Script -> Retry.

### Phase 3: Evolutionary Memory (Growth)

- **Status**: _Future_
- **Goal**: System capabilities grow linearly with usage time.
- **Key Features**:
  - **Trace Compiler**: Monitor `Universal Solver` success traces.
  - **Auto-Coding**: Promote high-frequency traces into permanent `Omni Skill` (Python Classes).
  - **Skill Injection**: Automated Git PRs to merge learned skills into the codebase.

## 4. Code Architecture: Universal Solver

**Target File**: `packages/python/agent/src/omni/agent/core/evolution/universal_solver.py`

```python
"""
The Generalist Agent Implementation.
Inspired by GEA architecture and OS-Copilot's Configurator.
"""
from typing import List, Any
from langchain_core.messages import BaseMessage
from omni.core.skills.runtime.omni_cell import OmniCellRunner, Intent

class UniversalSolver:
    def __init__(self, model, runner: OmniCellRunner):
        self.model = model
        self.runner = runner

    async def solve(self, task: str, context: List[BaseMessage]) -> str:
        """
        Adaptive loop handling unknown tasks via OmniCell primitives.
        """
        # 1. Perception: Get structured OS state
        # "Where am I? What is around me?"
        env_state = await self.runner.execute("ls | to json", Intent.OBSERVE)

        # 2. Planning (Dynamic Chain-of-Thought)
        plan = await self._generate_nu_plan(task, env_state)

        # 3. Execution & Correction Loop
        max_retries = 3
        for attempt in range(max_retries):
            result = await self.runner.execute(plan.script, Intent.MUTATE)

            if result.success:
                # 4. Success Signal -> Trigger Evolution Check
                return f"Task completed. Output: {result.data}"

            # Self-Correction based on stderr
            plan = await self._refine_plan(plan, result.error)

        return "Failed to adapt to task after retries."
```

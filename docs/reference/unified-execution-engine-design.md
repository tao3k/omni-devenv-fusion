# Omni-Dev-Fusion Unified Execution Engine Redesign

## LangGraph + Omega Architecture Integration Based on MemRL Paper

> **Status**: Draft
> **Version**: v1.1 | 2026-02-15
> **Related Paper**: [MemRL: Self-Evolving Agents via Runtime Reinforcement Learning on Episodic Memory](https://arxiv.org/abs/2601.03192)

---

## 1. Theoretical Foundation (MemRL Paper Validation)

### 1.1 Core Research Question

**How can an Agent continuously self-evolve at runtime without modifying model weights?**

### 1.2 MemRL Core Mechanisms

| Mechanism                             | Paper Description                                       | Our Implementation                |
| ------------------------------------- | ------------------------------------------------------- | --------------------------------- |
| **Intent-Experience-Utility Triplet** | Memory organized as (intent, experience, utility value) | Episode Store                     |
| **Two-Phase Retrieval**               | Phase A: Semantic recall → Phase B: Q-value reranking   | Recall Workflow                   |
| **Q-Value Learning**                  | Update Q-values through environmental feedback          | Evolve Workflow                   |
| **Stability-Plasticity**              | Freeze LLM, only update memory                          | Stable reasoning + Plastic memory |
| **LLM-Driven Workflow Composition**   | LLM decides workflow combination                        | Self-Evolving Engine              |

### 1.3 Theoretical Guarantee

MemRL paper Theorem A.1 proves Q-value convergence:

```
Q_new = Q_old + α(r - Q_old)

Convergence conditions:
1. Frozen LLM (Inference Policy)
2. Fixed task distribution
3. Continuous updates
```

---

## 2. Core Architecture

### 2.1 Design Principles

```
1. Separation: Stable reasoning + Plastic memory
2. Learning: Update Q-values through reward signals
3. Filtering: Two-phase retrieval to reduce noise
4. Evolution: LLM-driven workflow composition + self-improvement
```

### 2.2 Modular Workflow Architecture

Each workflow is an independent LangGraph that can be freely composed:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Self-Evolving Engine                                      │
│                                                                             │
│   LLM Analyze → Compose Workflows → Execute → Reflect → Evolve           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│ Analyze      │          │ Plan         │          │ Recall       │
│ Workflow     │          │ Workflow     │          │ Workflow     │
│              │          │              │          │              │
│ - intent     │          │ - complexity │          │ - Phase 1    │
│   parsing    │          │   analysis   │          │   semantic   │
│ - embedding  │          │ - DAG        │          │ - Phase 2    │
│ - classify   │          │   decompose  │          │   Q-filter   │
└──────────────┘          └──────────────┘          └──────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   Execute Workflow    │
                        │   (ReAct Loop)       │
                        │                       │
                        │ - Think               │
                        │ - Action              │
                        │ - Observe             │
                        │ - Reflect → Continue │
                        └───────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │  Evaluate + Evolve    │
                        │                       │
                        │ - Reward = 0/1       │
                        │ - Q = Q + α(r-Q)     │
                        │ - Store episode       │
                        └───────────────────────┘
```

---

## 3. Independent Workflows

### 3.1 Analyze Workflow

```python
# workflows/analyze.py
"""
Intent Analysis Workflow
- Parse user task
- Generate embedding
- Classify task type
"""

class AnalyzeWorkflow:
    @staticmethod
    def build() -> StateGraph:
        graph = StateGraph(AnalyzeState)

        # Nodes
        graph.add_node("parse", parse_intent)
        graph.add_node("embed", generate_embedding)
        graph.add_node("classify", classify_task_type)

        # Edges
        graph.set_entry_point("parse")
        graph.add_edge("parse", "embed")
        graph.add_edge("embed", "classify")

        return graph.compile()
```

### 3.2 Plan Workflow

```python
# workflows/plan.py
"""
Task Planning Workflow
- Analyze complexity
- Decompose into DAG
- Identify parallel opportunities
"""

class PlanWorkflow:
    @staticmethod
    def build() -> StateGraph:
        graph = StateGraph(PlanState)

        graph.add_node("complexity", analyze_complexity)
        graph.add_node("decompose", decompose_dag)
        graph.add_node("parallelize", identify_parallel)

        graph.set_entry_point("complexity")
        graph.add_edge("complexity", "decompose")
        graph.add_edge("decompose", "parallelize")

        return graph.compile()
```

### 3.3 Recall Workflow (Core - Two-Phase)

```python
# workflows/recall.py
"""
Memory Recall Workflow - MemRL Core
Phase 1: Semantic recall (find similar candidates)
Phase 2: Q-value filter (rank by utility)
"""

class RecallWorkflow:
    @staticmethod
    def build() -> StateGraph:
        graph = StateGraph(RecallState)

        graph.add_node("semantic", phase1_semantic_recall)
        graph.add_node("qfilter", phase2_qvalue_filter)
        graph.add_node("rank", rank_by_score)

        graph.set_entry_point("semantic")
        graph.add_edge("semantic", "qfilter")
        graph.add_edge("qfilter", "rank")

        return graph.compile()


# Phase 1: Semantic Recall (Rust)
async def phase1_semantic_recall(state: RecallState) -> RecallState:
    embedding = await rust.encode_intent(state["task"])
    candidates = await rust.semantic_recall(embedding, top_k=10)
    state["candidates"] = candidates
    return state


# Phase 2: Q-Value Filter (MemRL Core)
async def phase2_qvalue_filter(state: RecallState) -> RecallState:
    scored = []
    for ep in state["candidates"]:
        # score = (1-λ)*sim + λ*Q
        score = (1 - state["lambda"]) * ep.similarity + state["lambda"] * ep.q_value
        scored.append((ep, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    state["filtered"] = [ep for ep, _ in scored[:state["top_k"]]]
    return state
```

### 3.4 Execute Workflow (ReAct Loop)

```python
# workflows/execute.py
"""
Execution Workflow - ReAct Loop
Includes Reflection for self-correction
"""

class ExecuteWorkflow:
    @staticmethod
    def build(max_turns: int = 10) -> StateGraph:
        graph = StateGraph(ExecuteState)

        graph.add_node("think", think_node)
        graph.add_node("action", action_node)
        graph.add_node("observe", observe_node)
        graph.add_node("reflect", reflect_node)

        graph.set_entry_point("think")

        # Loop: think → action → observe → reflect → (continue or end)
        graph.add_edge("think", "action")
        graph.add_edge("action", "observe")
        graph.add_edge("observe", "reflect")

        # Conditional: continue based on reflection
        graph.add_conditional_edges(
            "reflect",
            should_continue,
            {"think": "think", "END": END}
        )

        return graph.compile()


async def reflect_node(state: ExecuteState) -> ExecuteState:
    """Reflection: Critical for self-correction"""
    reflection = await llm.reflect(
        task=state["task"],
        steps=state["steps"],
        memory=state.get("episodes", [])
    )
    state["reflection"] = reflection
    return state


def should_continue(state: ExecuteState) -> str:
    """Decide whether to continue or end"""
    if len(state["steps"]) >= state.get("max_turns", 10):
        return "END"

    reflection = state.get("reflection", "")
    if "success" in reflection.lower():
        return "END"
    elif "fail" in reflection.lower():
        return "END"

    return "think"  # Continue
```

### 3.5 Evaluate Workflow

```python
# workflows/evaluate.py
"""
Evaluation Workflow
Compute reward from execution result
"""

class EvaluateWorkflow:
    @staticmethod
    def build() -> StateGraph:
        graph = StateGraph(EvaluateState)

        graph.add_node("check", check_completion)
        graph.add_node("compute", compute_reward)
        graph.add_node("classify", classify_success)

        graph.set_entry_point("check")
        graph.add_edge("check", "compute")
        graph.add_edge("compute", "classify")

        return graph.compile()


async def compute_reward(state: EvaluateState) -> EvaluateState:
    """Compute reward: 1.0 if success, 0.0 if failure"""
    if state["completed"]:
        state["reward"] = 1.0
    else:
        state["reward"] = 0.0

    return state
```

### 3.6 Evolve Workflow (Q-Learning)

```python
# workflows/evolve.py
"""
Evolution Workflow - MemRL Core
Q-Learning: Q_new = Q_old + α*(reward - Q_old)
Store new episodes
"""

class EvolveWorkflow:
    @staticmethod
    def build() -> StateGraph:
        graph = StateGraph(EvolveState)

        graph.add_node("update_q", update_q_values)
        graph.add_node("store_success", store_successful_episode)
        graph.add_node("store_failure", store_failure_reflection)
        graph.add_node("merge", merge_to_history)

        graph.set_entry_point("update_q")
        graph.add_edge("update_q", "store_success")
        graph.add_edge("update_q", "store_failure")
        graph.add_edge("store_success", "merge")
        graph.add_edge("store_failure", "merge")
        graph.add_edge("merge", END)

        return graph.compile()


async def update_q_values(state: EvolveState) -> EvolveState:
    """
    Core Q-Learning formula: Q_new = Q_old + α*(r - Q_old)
    """
    alpha = state.get("learning_rate", 0.3)

    for ep in state["used_episodes"]:
        q_old = ep.q_value
        reward = state["reward"]
        q_new = q_old + alpha * (reward - q_old)

        # Update in Rust backend
        await rust.update_q_value(ep.id, q_new, reward)

    state["q_updates"] = [(ep.id, q_new) for ep in state["used_episodes"]]
    return state


async def store_successful_episode(state: EvolveState) -> EvolveState:
    """Store successful execution as new episode"""
    if state["reward"] > 0 and state["steps"]:
        episode = Episode(
            id=str(uuid.uuid4()),
            intent=state["task"],
            experience=serialize_steps(state["steps"]),
            q_value=state["reward"],
            success_count=1,
            failure_count=0
        )
        await rust.index_episode(episode)
        state["new_episode"] = episode

    return state
```

---

## 4. LLM-Driven Workflow Composition

### 4.1 Core Innovation: Self-Evolving Workflow

The key innovation is using LLM to compose and evolve workflows:

```python
# workflow_evolution.py

class WorkflowEvolution:
    """
    LLM-Driven Workflow Self-Evolution
    Core: Let LLM decide workflow composition and learn from results
    """

    def __init__(self, llm, episode_store):
        self.llm = llm
        self.episode_store = episode_store

    async def analyze_and_compose(self, task: str) -> list[str]:
        """
        LLM analyzes task and decides which workflows to use
        """
        # Get historical experiences
        history = await self.episode_store.get_recent(limit=5)

        prompt = f"""
Task: {task}

Available workflows:
- analyze: Intent analysis
- plan: Task decomposition
- recall: Two-phase memory recall
- execute: ReAct execution loop
- evaluate: Result evaluation
- evolve: Q-Learning and self-evolution

Recent history:
{self._format_history(history)}

Decide which workflows to use for this task.
Return as comma-separated list.

Examples:
- Simple task: "analyze,execute,evaluate"
- Complex task: "analyze,plan,recall,execute,evaluate,evolve"
- Exploration: "analyze,recall,execute,evolve"
"""

        response = await self.llm.generate(prompt)
        workflows = self._parse_response(response)

        return workflows

    async def reflect_and_evolve(self, task: str, workflows: list[str],
                                 result: ExecutionResult) -> EvolutionFeedback:
        """
        LLM reflects on execution result and suggests workflow improvements
        """
        prompt = f"""
Task: {task}
Workflows used: {workflows}
Success: {result.success}
Steps: {len(result.steps)}
Failure reason: {result.failure_reason or "none"}

Analyze what went wrong and suggest improvements:

1. Was task decomposition adequate?
2. Was memory recall useful?
3. Was reflection helpful?
4. What workflow changes would improve results?

Return as JSON:
{{
  "improvement": "description",
  "new_workflows": "comma-separated list",
  "learned_lesson": "key insight"
}}
"""

        feedback = await self.llm.generate_json(prompt)

        # Store learned lesson
        await self.episode_store.store_lesson(
            task_type=extract_task_type(task),
            lesson=feedback["learned_lesson"],
            workflow_adjustment=feedback["new_workflows"]
        )

        return EvolutionFeedback(**feedback)
```

### 4.2 Self-Evolving Engine

```python
# self_evolving_engine.py

class SelfEvolvingEngine:
    """
    Self-Evolving Execution Engine
    Core: LLM-driven workflow composition + continuous learning
    """

    def __init__(self, llm, episode_store):
        self.evolution = WorkflowEvolution(llm, episode_store)
        self.composer = WorkflowComposer()
        self.history = []

    async def run(self, task: str) -> ExecutionResult:
        # Phase 1: LLM analyzes and composes workflows
        workflows = await self.evolution.analyze_and_compose(task)

        # Phase 2: Build and execute
        graph = self.composer.compose(workflows)
        result = await graph.ainvoke({"task": task})

        # Phase 3: Record history
        self.history.append({
            "task": task,
            "workflows": workflows,
            "result": result
        })

        # Phase 4: Reflect and evolve (if failed or complex)
        if not result.success or len(result.steps) > 5:
            feedback = await self.evolution.reflect_and_evolve(
                task, workflows, result
            )

            # Store workflow preference for similar tasks
            await self.episode_store.store_workflow_preference(
                task_type=extract_task_type(task),
                preferred_workflows=feedback.new_workflows
            )

        return result
```

---

## 5. Workflow Composer

```python
# composer.py

class WorkflowComposer:
    """
    Compose independent workflows into executable graph
    """

    WORKFLOWS = {
        "analyze": AnalyzeWorkflow,
        "plan": PlanWorkflow,
        "recall": RecallWorkflow,
        "execute": ExecuteWorkflow,
        "evaluate": EvaluateWorkflow,
        "evolve": EvolveWorkflow,
    }

    @classmethod
    def compose(cls, workflow_names: list[str]) -> CompiledGraph:
        """Compose multiple workflows into one graph"""
        graph = StateGraph(OmegaState)

        for name in workflow_names:
            workflow_cls = cls.WORKFLOWS[name]
            sub_graph = workflow_cls.build()
            graph = cls._merge(graph, sub_graph)

        return graph.compile()

    @classmethod
    def compose_standard(cls) -> CompiledGraph:
        """Standard: analyze → plan → recall → execute → evaluate → evolve"""
        return cls.compose([
            "analyze", "plan", "recall",
            "execute", "evaluate", "evolve"
        ])

    @classmethod
    def compose_simple(cls) -> CompiledGraph:
        """Simple: analyze → execute → evaluate"""
        return cls.compose(["analyze", "execute", "evaluate"])

    @classmethod
    def compose_explore(cls) -> CompiledGraph:
        """Exploration: analyze → recall → execute → evolve"""
        return cls.compose(["analyze", "recall", "execute", "evolve"])
```

---

## 6. Rust Backend

### 6.1 Episode Store

```rust
// episode_store.rs

pub struct EpisodeStore {
    lance: LanceDB,
    q_table: QTable,
}

impl EpisodeStore {
    pub async fn new() -> Self {
        Self {
            lance: LanceDB::new().await,
            q_table: QTable::new(),
        }
    }

    pub async fn index_episode(&self, episode: Episode) -> Result<(), Error> {
        self.lance.insert("episodes", episode).await
    }

    pub async fn semantic_recall(&self, embedding: Vec<f32>, top_k: usize)
        -> Vec<Episode> {
        self.lance.search("episodes", embedding, top_k).await
    }

    pub fn update_q(&self, id: &str, reward: f32) -> f32 {
        self.q_table.update(id, reward)
    }

    pub fn get_q(&self, id: &str) -> f32 {
        self.q_table.get(id).unwrap_or(0.5)
    }
}
```

### 6.2 Two-Phase Search

```rust
// two_phase_search.rs

pub async fn two_phase_search(
    &self,
    embedding: Vec<f32>,
    k1: usize,
    k2: usize,
    lambda: f32,
) -> Vec<Episode> {
    // Phase 1: Semantic recall
    let candidates = self.episode_store.semantic_recall(embedding.clone(), k1);

    // Phase 2: Q-value reranking
    let mut scored: Vec<(Episode, f32)> = candidates
        .iter()
        .map(|ep| {
            let sim = ep.similarity;
            let q = self.episode_store.get_q(&ep.id);
            let score = (1.0 - lambda) * sim + lambda * q;
            (ep.clone(), score)
        })
        .collect();

    scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    scored.into_iter().take(k2).map(|(ep, _)| ep).collect()
}
```

---

## 7. Complete Execution Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                    Self-Evolving Engine                                 │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│  1. LLM Analyze Task                                                  │
│     "This is a complex debugging task, needs recall + evolve"        │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│  2. Compose Workflows                                                 │
│     [analyze, recall, execute, evaluate, evolve]                     │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│  3. Execute Workflow                                                  │
│     ├─ Analyze: intent parsing + embedding                           │
│     ├─ Recall: Two-phase (semantic + Q-filter)                      │
│     ├─ Execute: ReAct loop with reflection                          │
│     ├─ Evaluate: reward = 1.0 or 0.0                               │
│     └─ Evolve: Q = Q + α(r-Q), store episode                       │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│  4. LLM Reflect (if failed)                                          │
│     "Failed because memory recall didn't find relevant code"         │
│     "Next time: add plan workflow before execute"                   │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                    Next similar task uses optimized workflow
```

---

## 8. Implementation Plan

### Phase 1: Infrastructure (1 week)

- [ ] Episode Store Rust implementation
- [ ] Two-Phase Search Rust implementation
- [ ] Q-Table Rust implementation

### Phase 2: Workflow Development (2 weeks)

- [ ] Analyze Workflow
- [ ] Plan Workflow
- [ ] Recall Workflow (Two-Phase)
- [ ] Execute Workflow (ReAct + Reflection)
- [ ] Evaluate Workflow
- [ ] Evolve Workflow (Q-Learning)

### Phase 3: Composer + Evolution (1 week)

- [ ] Workflow Composer
- [ ] LLM-Driven Workflow Composition
- [ ] Self-Evolving Engine

### Phase 4: Integration + Testing (1 week)

- [ ] End-to-end integration
- [ ] Benchmark tests
- [ ] Validation experiments

---

## 9. Summary

This design implements MemRL's core principles:

1. **Separation**: Stable reasoning (LLM) + Plastic memory (Episodes)
2. **Two-Phase Retrieval**: Semantic recall + Q-value filtering
3. **Q-Learning**: Q_new = Q_old + α(r - Q_old)
4. **Self-Evolution**: LLM-driven workflow composition + reflection

The modular architecture allows:

- Independent workflow development
- Free composition for different tasks
- Continuous learning and optimization

Theoretical feasibility is guaranteed by MemRL paper.

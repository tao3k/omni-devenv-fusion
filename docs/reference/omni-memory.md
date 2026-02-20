# Omni-Memory: Self-Evolving Memory Engine

> Rust-based Self-Evolving Memory with Q-Learning and Two-Phase Search
> **Status**: Implemented
> **Version**: v1.0 | 2026-02-15

## Overview

This document describes the implementation of **omni-memory**, a Rust-based self-evolving memory engine inspired by the [MemRL paper](https://arxiv.org/abs/2601.03192).

### Core Features

| Feature             | Status | Description                                   |
| ------------------- | ------ | --------------------------------------------- |
| Episode Storage     | ✅     | Vector similarity search on episodic memories |
| Q-Learning          | ✅     | Q-value updates based on reward signals       |
| Two-Phase Search    | ✅     | Semantic recall → Q-value reranking           |
| Intent Encoding     | ✅     | Hash-based intent embedding                   |
| Memory Decay        | ✅     | Forgets stale episodes over time              |
| Multi-hop Reasoning | ✅     | Chain multiple queries for complex reasoning  |
| JSON Persistence    | ✅     | Save/load episodes to disk                    |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Python Layer (Orchestration)             │
│  - Workflow orchestration                                    │
│  - State management                                         │
│  - LLM interaction                                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Rust Layer (omni-memory)                 │
├─────────────────────────────────────────────────────────────┤
│  episode.rs     - Episode data structure                    │
│  q_table.rs     - Q-Learning core (DashMap + RwLock)       │
│  store.rs       - Episode storage + search                  │
│  two_phase.rs   - Two-phase search (CORE)                  │
│  encoder.rs     - Intent encoding (hash-based)              │
└─────────────────────────────────────────────────────────────┘
```

### Modularization Rule

Persistent-memory code must follow directory-level sub-module design:

- `mod.rs` files define interfaces/re-exports only.
- implementation belongs to focused sub-modules (and nested folders when needed).
- avoid monolithic files for mixed concerns; split by capability (encoding, storage, policy, lifecycle).
- keep tests in dedicated `tests/` files mapped to each module.

### Namespace Design

Following existing patterns (`omni-vector`, `xiuxian-wendao`):

```
omni::memory          # Core memory module
├── episode           # Episode data structure
├── q_table           # Q-Learning core
├── store             # Episode storage (LanceDB-ready)
├── two_phase         # Two-phase search (CORE)
└── encoder           # Intent encoding
```

---

## MemRL Claims vs Implementation

### Claim 1: Self-Evolution via RL on Episodic Memory

| MemRL Claim                                  | Our Implementation                                  |
| -------------------------------------------- | --------------------------------------------------- |
| Two-phase retrieval: recall → utility filter | ✅ `two_phase_recall()`                             |
| Environmental feedback (reward signal)       | ✅ `update_q()`, `mark_success()`, `mark_failure()` |
| No weight updates                            | ✅ Non-parametric, all learning in memory           |
| Addresses stability-plasticity dilemma       | ✅ Stable reasoning, plastic memory                 |

**Our Enhancement**: We added **memory decay** and **multi-hop reasoning**, which are not in the original MemRL paper.

### Claim 2: Two-Phase Retrieval

```
Phase 1: Semantic Recall (k1 candidates)
    │
    ▼
    ┌─────────────────────────────────────────────┐
    │  Vector similarity search                   │
    │  Find k1 most similar episodes             │
    └─────────────────────────────────────────────┘
    │
    ▼
Phase 2: Q-Value Reranking (k2 results)
    │
    ▼
    ┌─────────────────────────────────────────────┐
    │  Score = (1-λ) × similarity + λ × Q-value  │
    │  Sort by combined score                     │
    │  Return top k2                              │
    └─────────────────────────────────────────────┘
```

### Claim 3: Q-Learning Algorithm

```
Q_new = Q_old + α × (reward - Q_old)

Where:
- α (alpha) = learning_rate (default: 0.2)
- reward = 1.0 (success) or 0.0 (failure)
- Q_old = current Q-value (default: 0.5)
```

---

## API Reference

### Python Service

**File**: `packages/python/agent/src/omni/agent/services/memory.py`

```python
from omni.agent.services.memory import MemoryService, MemoryConfig, MemoryEpisode

# Configuration
config = MemoryConfig(
    embedding_dim=384,
    k1=20,  # Phase 1 candidates
    k2=5,   # Phase 2 results
    q_weight=0.3,  # λ weight for Q-value
    learning_rate=0.2,
    discount_factor=0.95,
)

# Create service
memory = MemoryService(config)

# Store episode
episode_id = memory.store_episode(
    intent="debug network timeout",
    experience="Increased timeout to 30s",
    outcome="success"
)

# Semantic recall
results = memory.recall("fix timeout error", k=5)

# Two-phase recall (semantic + Q-value)
results = memory.two_phase_recall("fix timeout error", k1=20, k2=5, q_weight=0.3)

# Multi-hop reasoning
results = memory.multi_hop_recall(
    queries=["debug api error", "fix timeout", "network issue"],
    k=3
)

# Update Q-value
memory.mark_success(episode_id)  # reward = 1.0
memory.mark_failure(episode_id)  # reward = 0.0
```

### Rust Core

**File**: `packages/rust/crates/omni-memory/src/lib.rs`

```rust
// Create components
let encoder = create_intent_encoder(384);
let q_table = create_q_table(0.2, 0.95);
let store = create_episode_store(config);

// Store episode
let episode = create_episode(id, intent, experience, outcome);
store.store(episode);

// Two-phase recall
let results = store.two_phase_recall_with_embedding(embedding, k1, k2, lambda);

// Update Q-value
store.update_q(episode_id, reward);
```

---

## Performance Characteristics

| Operation        | Complexity    | Notes                              |
| ---------------- | ------------- | ---------------------------------- |
| Episode store    | O(1)          | HashMap lookup                     |
| Semantic recall  | O(n)          | Linear scan with cosine similarity |
| Two-phase recall | O(n × log k1) | Sort k1 candidates                 |
| Q-value update   | O(1)          | DashMap update                     |
| Memory decay     | O(n)          | Linear scan all episodes           |

---

## File Structure

```
packages/rust/crates/omni-memory/
├── Cargo.toml
├── src/
│   ├── lib.rs           # Exports
│   ├── episode.rs       # Episode struct
│   ├── q_table.rs       # Q-Learning
│   ├── store.rs         # Episode storage
│   ├── two_phase.rs     # Two-phase search
│   ├── encoder.rs       # Intent encoding
│   └── pymodule_impl.rs # PyO3 bindings
└── tests/
    └── test_memory_engine.rs

packages/python/agent/src/omni/agent/services/
└── memory.py            # Python service layer
```

---

## Testing

### Rust Tests

```bash
cargo test -p omni-memory
```

### Python Tests

```bash
uv run pytest packages/python/agent/tests/unit -k memory -v
```

---

## Comparison with MemRL

| Dimension       | MemRL                        | Omni-Memory                              |
| --------------- | ---------------------------- | ---------------------------------------- |
| Memory type     | Episodic (trajectories)      | Episodes (intent + experience + outcome) |
| Retrieval       | Two-phase (recall + utility) | Two-phase (semantic + Q-value)           |
| Feedback        | Environmental (reward)       | Explicit (mark_success/failure)          |
| Reasoning       | Frozen                       | Frozen (no fine-tuning)                  |
| Plastic part    | Episodic memory              | Episodes + Q-table                       |
| **Enhancement** | -                            | Memory decay                             |
| **Enhancement** | -                            | Multi-hop reasoning                      |
| **Enhancement** | -                            | JSON persistence                         |

---

## Related Documentation

- [MemRL vs Omni-Memory Research](./research-memrl-vs-omni-memory.md)
- [Memory Mesh](./memory-mesh.md)
- [Hippocampus](./hippocampus.md)

# Cognitive Pipeline Architecture

> Layered Assembly Engine for LLM System Prompts

## 1. Overall Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLM System Prompt                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  <role>You are a master software architect.</role>                       │ │  ← SystemPersonaProvider (priority=0)
│  │                                                                          │ │
│  │  <active_protocol>                                                       │ │  ← ActiveSkillProvider (priority=10)
│  │  # Active Protocol                                                       │ │
│  │  ---                                                                     │ │
│  │  name: "researcher"                                                      │ │
│  │  ...SKILL.md content...                                                  │ │
│  │  </active_protocol>                                                      │ │
│  │                                                                          │ │
│  │  <available_tools>                                                       │ │  ← AvailableToolsProvider (priority=20)
│  │  - researcher: Sharded Deep Research...                                  │ │
│  │  - git: Git operations...                                                │ │
│  │  ...                                                                     │ │
│  │  </available_tools>                                                      │ │
│  │                                                                          │ │
│  │  [RAG Knowledge]                                                         │ │  ← EpisodicMemoryProvider (priority=40)
│  │  ...similar past experiences...                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. Layered Design

| Layer    | Provider               | Priority    | Responsibility          | Source                                  |
| -------- | ---------------------- | ----------- | ----------------------- | --------------------------------------- |
| **L0**   | SystemPersonaProvider  | 0 (highest) | Role definition         | Hardcoded personas                      |
| **L1.5** | ActiveSkillProvider    | 10          | Current skill protocol  | `skills/{skill}/SKILL.md`               |
| **L2**   | AvailableToolsProvider | 20          | Available tools index   | Rust Scanner `skill-index.json`         |
| **L4**   | EpisodicMemoryProvider | 40          | RAG knowledge retrieval | [Hippocampus](hippocampus.md) (LanceDB) |

**Composition Order**: Sorted by priority ascending, concatenated into complete system prompt.

## 3. Data Flow

```
User Request (@omni)
       │
       ▼
┌─────────────────────────────┐
│  LangGraph Workflow         │
│  (research_graph.py)        │
└────────────┬──────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────┐
│  node_architect()                                        │
│  1. Call ContextOrchestrator.build_context(state)       │──┐
│  2. Execute all Providers in parallel                   │  │
│  3. Sort results by priority                            │  │
│  4. Concatenate into system_prompt                      │  │
│  5. Store in state["system_prompt"] (cache)             │  │
└──────────────────────────────────────────────────────────┘  │
             │                                           │
             ▼                                           │
┌──────────────────────────────────────────────────────────┐
│  node_process_shard()                                    │
│  1. Get cached context from state["system_prompt"]       │◄─┘
│  2. + shard-specific code compression (repomix)          │
│  3. Call LLM complete(system_prompt, user_query)         │
└──────────────────────────────────────────────────────────┘
```

## 4. Provider Details

### 4.1 SystemPersonaProvider (L0)

```python
DEFAULT_PERSONAS = {
    "architect": "<role>You are a master software architect.</role>",
    "developer": "<role>You are an expert developer.</role>",
    "researcher": "<role>You are a thorough researcher.</role>",
}
```

**Responsibility**: Define LLM's base role/persona.

### 4.2 ActiveSkillProvider (L1.5)

```
Skill Directory: assets/skills/{skill_name}/
         ├── SKILL.md          ← Main protocol file
         ├── prompts/          ← Prompt templates
         ├── scripts/          ← Tool implementations
         └── required_refs/    ← Optional reference files
```

**Responsibility**: Load the complete protocol for the active skill (SKILL.md + required_refs).

**Implementation**:

```python
# packages/python/core/src/omni/core/context/providers.py
class ActiveSkillProvider:
    async def provide(self, state, budget) -> ContextResult:
        skill_name = state["active_skill"]  # e.g., "researcher"
        content = SkillMemory().hydrate_skill_context(skill_name)
        # Returns <active_protocol>{content}</active_protocol>
```

### 4.3 AvailableToolsProvider (L2)

```
Rust Scanner → skill-index.json (generated once)
                    │
                    ▼
            SkillIndexLoader (Python)
                    │
                    ▼
        Available tools list (name, description, schema)
```

**Responsibility**: Tell LLM what tools are available.

### 4.4 EpisodicMemoryProvider (L4)

```
User Request/State → Vector Search (LanceDB) → Similar Past Experiences → Context
```

**Responsibility**: RAG retrieval of past experiences.

## 5. Rust-Powered Context Assembly

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Rust ContextAssembler                           │
│  (omni-io/src/assembler.rs)                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Parallel I/O (rayon)                                           │
│     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│     │ SKILL.md    │ +   │ ref1.md     │ +   │ ref2.md     │       │
│     └─────────────┘     └─────────────┘     └─────────────┘       │
│                                                                     │
│  2. Templating (minijinja)                                         │
│     {{ skill.name }} → "researcher"                                │
│     {{ skill.version }} → "2.0.0"                                  │
│                                                                     │
│  3. Token Counting (omni-tokenizer)                                │
│     → Returns token_count for budget management                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
    Python Binding (PyContextAssembler)
         │
         ▼
    SkillMemory.hydrate_skill_context()
```

## 6. Code Locations

```
packages/python/core/src/omni/core/context/
├── __init__.py           # Public API exports
├── base.py               # ContextProvider, ContextResult (abstract base classes)
├── providers.py          # 4 Provider implementations
└── orchestrator.py       # ContextOrchestrator (parallel fetch → serial assembly)

packages/python/core/src/omni/core/skills/
├── memory.py             # SkillMemory (Rust ContextAssembler Facade)
├── index_loader.py       # skill-index.json loader
├── file_cache.py         # File caching
└── ref_parser.py         # required_refs parsing

packages/rust/crates/omni-io/src/
└── assembler.rs          # Rust ContextAssembler (parallel I/O + templating + token)

packages/rust/bindings/python/src/
└── context.rs            # PyContextAssembler Python bindings
```

## 7. Log Example

```
# During researcher skill execution
[INFO] Context providers output
  providers=[
    {name: 'persona', priority: 0, tokens: 6, chars: 49},
    {name: 'active_skill', priority: 10, tokens: 342, chars: 3161},
    {name: 'tools', priority: 20, tokens: 50, chars: 200},
    {name: 'rag', priority: 40, tokens: 0, chars: 0},
  ]
  total_tokens=448

# Meaning:
# - persona: Role definition (6 tokens)
# - active_skill: researcher SKILL.md (342 tokens) ← The protocol you're looking for
# - tools: Available tools list (50 tokens)
# - rag: RAG retrieval results (0 tokens, budget exceeded)
```

## 8. FAQ

### Q: Why not rebuild context for every shard?

A: **Performance optimization**. Skill context (SKILL.md) doesn't change during workflow, only built once in `node_architect`, stored in `state["system_prompt"]` cache, subsequent shards reuse it directly.

### Q: What's the difference between SystemPersona and ActiveSkill?

|                      | SystemPersona    | ActiveSkill                      |
| -------------------- | ---------------- | -------------------------------- |
| **Source**           | Hardcoded string | `skills/researcher/SKILL.md`     |
| **Change Frequency** | Almost never     | Changes when skill switches      |
| **Content**          | Role definition  | Skill protocol, tool definitions |

### Q: How to add a new Provider?

```python
# 1. Define in providers.py
class NewProvider(ContextProvider):
    priority = 30  # Choose appropriate priority
    async def provide(self, state, budget) -> ContextResult:
        # Implement logic
        return ContextResult(content="...", token_count=10, name="new", priority=30)

# 2. Register in orchestrator.py
def create_planner_orchestrator():
    return ContextOrchestrator([
        SystemPersonaProvider(role="architect"),
        NewProvider(),  # New addition
        ActiveSkillProvider(),
        ...
    ])
```

## 9. Related Documentation

- [Hippocampus](../human/architecture/hippocampus.md) - Memory Interface documentation
- [Skill Standard](docs/human/architecture/skill-standard.md)
- [LangGraph Workflow](../architecture/langgraph.md)
- [Rust-Python Bridge](rust-python-bridge.md)
- [Context Optimization](context-optimization.md)

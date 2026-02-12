# Omni Loop: CCA Runtime Architecture with RAG

> **Summary**: The Omni Loop is the core runtime orchestrator that implements the CCA (Context-Command-Action) pattern with **The Cognitive Loop** - enabling intelligent agent behavior through Observe-Decide-Act-Reflect cycles with RAG-powered knowledge augmentation and built-in anti-confusion mechanisms.

---

## 1. The Context (The "Why")

### The Pain Point

Early agent implementations suffered from the **Agent Confusion Loop**:

- Agents repeatedly read the same files without taking action
- No state tracking led to redundant operations
- Tool calls were not validated, causing wasted LLM calls
- Hardcoded logic made the system rigid and unmaintainable
- Agents lacked access to project-specific knowledge and best practices

### The Goal

Build a runtime that:

- Prevents redundant operations through intelligent state tracking
- Uses interceptor patterns for clean separation of concerns
- Enables dynamic skill injection based on task intent
- **Retrieves relevant knowledge before responding (RAG)**
- Maintains clean architecture for easy testing and extension

---

## 2. The Mental Model (The "What")

### The Analogy

Think of the Omni Loop as an **intelligent conductor** for an orchestra:

- **LoopState** is the conductor's score sheet, tracking what has been played (read) and modified
- **ActionGuard** is the rehearsal director, blocking repetitive passages
- **SkillInjector** dynamically invites the right musicians (skills) for each piece (task)
- **OmniLoop** conducts the performance through the OODA cycle

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        OmniLoop (CCA Runtime)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              The Cognitive Loop (RAG-Enhanced)          │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   │   │
│  │  │   Observe   │ → │   Decide    │ → │    Act      │   │   │
│  │  │ Build Ctx + │   │ LLM Reason  │   │ Execute     │   │   │
│  │  │ Retrieve    │   │ + Knowledge │   │ Tools       │   │   │
│  │  │ Knowledge   │   │ Augment     │   │             │   │   │
│  │  └─────────────┘   └─────────────┘   └─────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │
│  │ LoopState   │  │ ActionGuard │  │   SkillInjector     │    │
│  │ - visited   │  │ - check()   │  │   - Name Boosting   │    │
│  │ - modified  │  │ - update()  │  │   - Hybrid Search   │    │
│  └─────────────┘  └─────────────┘  └─────────────────────┘    │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              The Librarian (RAG Engine)                 │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │ _needs_knowledge() → Detect intent              │    │   │
│  │  │ _augment_context() → Search + Inject Knowledge  │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  │              ↓ Vector Store (Rust-powered)              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              ToolLoader (Rust Scanner)                  │   │
│  │  - JIT execution via omni_core_rs                       │   │
│  │  - Schema generation for LLM                            │   │
│  │  - Tool aliases management                              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. How It Works (The Mechanics)

### Core Components

#### LoopState (State Pattern)

Tracks session state using Sets for O(1) lookups:

```python
class LoopState:
    visited_files: Set[str]   # Files that have been read
    modified_files: Set[str]  # Files that have been modified

    def is_redundant_read(self, path: str) -> bool:
        """Read is redundant if: read before AND not modified since."""
        return path in self.visited_files and path not in self.modified_files
```

**Value**: Prevents repeated file reads, reducing token waste and LLM confusion.

#### ActionGuard (Interceptor Pattern)

Intercepts tool calls before execution:

```python
class ActionGuard:
    def check(self, tool_name: str, tool_input: dict) -> Optional[str]:
        """Return warning message if action is redundant."""
        # Tool schema from @skill_command tells LLM which params to use
        # LLM generates correct input, we just validate
        if "read" in tool_name:
            paths = self._extract_paths(tool_input)
            for path in paths:
                if path and self._state.is_redundant_read(path):
                    return self._block_message(path)
        return None
```

**Value**: Provides actionable feedback to the LLM instead of silently failing.

#### SkillInjector (Hybrid Discovery)

Dynamically loads relevant skills based on task intent:

1. **Name Boosting**: Detect explicit skill mentions (e.g., "use git to...")
2. **Hybrid Search**: Vector + keyword search for relevance
3. **JIT Loading**: Load unloaded skills on-demand

**Value**: Only loads necessary skills, reducing context bloat.

### The CCA Loop Flow

```
User Task → OmniLoop.run()
    │
    ├─→ [Plan] AdaptivePlanner estimates steps
    │
    ├─→ [Observe] ContextOrchestrator builds layered context
    │   └─→ SkillInjector provides skill prompts
    │
    ├─→ [Decide] LLM reasons with context + tools
    │
    ├─→ [Act] Execute tools with ActionGuard validation
    │   ├─→ Guard.check() ──→ Block if redundant read
    │   └─→ Guard.update_state() ──→ Track visited/modified
    │
    ├─→ [Reflect] Note-Taker distills session wisdom
    │
    └─→ Return summary + active skills
```

### The Cognitive Loop: RAG Integration

The OmniLoop now includes **The Cognitive Loop** - RAG-powered knowledge augmentation that allows the agent to "consult references before answering."

#### Flow Diagram

```
User Query
    │
    ├─→ _needs_knowledge() ──→ [True?] ──→ _augment_context()
    │   │                              │
    │   │                              ├─→ Librarian.search(query)
    │   │                              ├─→ Get top-K results
    │   │                              └─→ Inject as system message
    │   │
    │   └───────────────────────────────→ Direct inference
    │
    └─→ Return response (augmented with knowledge)
```

#### Intent Detection (`_needs_knowledge`)

Detects if a query requires knowledge retrieval:

```python
knowledge_keywords = [
    "how to", "what is", "explain", "documentation",
    "guide", "tutorial", "example", "best practice",
    "architecture", "design", "reference", "api",
    "error", "fix", "debug", "config", "setting",
]

# Also detects question patterns
if query.startswith(("what", "how", "why", "?")):
    return True
```

#### Context Augmentation (`_augment_context`)

Searches knowledge base and injects results:

```python
async def _augment_context(self, task: str) -> int:
    results = await self._librarian.search(
        query=task,
        limit=self.config.knowledge_limit,  # default: 3
        threshold=self.config.knowledge_threshold,  # default: 0.5
    )

    # Build knowledge context
    knowledge_parts = ["## Relevant Knowledge\n"]
    for i, result in enumerate(results, 1):
        knowledge_parts.append(f"### Source {i}: {result.entry.source}")
        knowledge_parts.append(result.entry.content)

    # Inject as system message
    self.context.add_system_message("\n".join(knowledge_parts))
    return len(results)
```

#### Configuration

```python
@dataclass
class OmniLoopConfig:
    enable_rag: bool = True           # Enable RAG
    knowledge_limit: int = 3          # Max entries to retrieve
    knowledge_threshold: float = 0.5  # Minimum relevance score
```

#### Example Usage

```python
loop = OmniLoop()

# Knowledge-intensive query (triggers RAG)
response = await loop.run(
    "How does the Trinity Architecture work?"
)
# → Searches knowledge base first
# → Injects relevant docs into context
# → Generates informed response

# Simple command (skips RAG)
response = await loop.run("commit my changes")
# → Direct inference, no knowledge lookup
```

**Value**: Agent consults project knowledge before responding, providing accurate, context-aware answers grounded in documentation.

---

## 4. Runtime vs Evolution: omni run exec vs Meta-Agent

A common question: **What's the difference between `omni run exec` and `Meta-Agent`?**

The answer is fundamental to understanding the architecture:

> **`omni run exec` is the Driver; `Meta-Agent` is the Engineer.**

| Aspect              | omni run exec (Runtime)                              | Meta-Agent (Evolution)                                |
| ------------------- | ---------------------------------------------------- | ----------------------------------------------------- |
| **Core Engine**     | `OmniLoop` / `Orchestrator`                          | `MetaAgent` / `TDD Cycle`                             |
| **Primary Goal**    | **Solve problems** (Task Execution)                  | **Generate/fix capabilities** (Capability Generation) |
| **Work Mode**       | **Dispatch**: Route → Find Tool → Execute → Feedback | **TDD**: Write Test → Run → Fail → Fix → Pass         |
| **Missing Tool**    | Fails or uses generic LLM to "guess"                 | **Creates** a new tool from scratch                   |
| **Output**          | Answer, file edits, operation results                | Python code (`.py`), tests, fixed system              |
| **Codebase Access** | Read-Only (typically)                                | Read-Write (creates new files)                        |

### The Driver Analogy

```
┌─────────────────────────────────────────────────────────────────┐
│                    omni run exec (Driver)                       │
│                                                                 │
│  User: "Parse this .pcab file"                                  │
│                                                                 │
│  1. Check skill registry → No .pcab parser exists              │
│  2. Options:                                                    │
│     - FAIL: "I don't know .pcab format"                        │
│     - or: Use generic LLM to guess (unreliable)                │
│                                                                 │
│  Result: Cannot complete the task                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Meta-Agent (Engineer)                         │
│                                                                 │
│  Request: "Create a .pcab parser skill"                         │
│                                                                 │
│  1. TDD Cycle:                                                  │
│     - Write test: parse_sample() should extract IP addresses    │
│     - Run test → FAIL                                          │
│     - Generate code: `class PcabParser`                         │
│     - Run test → FAIL                                          │
│     - Analyze error → Fix code                                  │
│     - Repeat until PASS                                         │
│                                                                 │
│  2. Output:                                                     │
│     - `skills/network/pcab_parser.py` (new skill!)              │
│     - `skills/network/tests/test_pcab_parser.py`                │
│                                                                 │
│  Result: New capability created!                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    The Fusion: Self-Evolving Agent              │
│                                                                 │
│  User: "Parse this .pcab file"                                  │
│                                                                 │
│  1. omni run exec checks skills → .pcab parser NOT found        │
│  2. TRIGGERS Meta-Agent → "Create .pcab parser skill"          │
│  3. Meta-Agent generates skill → JIT loads into registry       │
│  4. omni run exec retries → SUCCESS                            │
│                                                                 │
│  Outcome: User gets result, system gains new capability        │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Distinction Matters

**`omni run exec` is the Conscious Mind** (handles tasks directly)

- Fast, focused, action-oriented
- Limited to existing tools
- Optimized for execution speed

**`Meta-Agent` is the Subconscious** (self-evolves and repairs)

- Slow, thorough, correctness-oriented
- Creates new tools when needed
- Optimized for code quality

Together, they form **F4: Self-Evolving Agent**:

- Fulfills immediate tasks (omni run exec)
- Adapts to new challenges (Meta-Agent)

---

## 6. Value Scenarios

### Scenario 1: Anti-Confusion Loop Prevention

**Problem**: Agent keeps re-reading the same file without acting.

```
Step 1: read_files(paths=["README.md"]) → Allowed, tracked
Step 2: read_files(paths=["README.md"]) → BLOCKED by ActionGuard
         → Returns: "Already read. Consider writing changes."
Step 3: write_file(path="README.md", ...) → Allowed, tracked
```

**Outcome**: Agent takes action instead of looping.

### Scenario 2: Dynamic Skill Injection

**Problem**: Loading all skills bloats context.

```
Task: "Fix the bug in auth.py with git commit"

1. Name Boosting detects: "git" skill mention
2. Hybrid search finds: "filesystem", "writer" relevant
3. JIT loads: git, filesystem, writer skills only

Context includes: Only 3 skill prompts (~1KB vs ~50KB for all)
```

**Outcome**: 50x context reduction for skill prompts.

### Scenario 3: Session State Tracking

**Problem**: Agent doesn't know what files it has already processed.

```
With LoopState:
- visited_files = {"README.md", "auth.py"}
- modified_files = {"auth.py"}

is_redundant_read("README.md") → True (read, not modified)
is_redundant_read("auth.py") → False (was modified)
```

**Outcome**: Agent can make informed decisions about re-reading files.

---

## 7. Design Decisions & Trade-offs

| Decision                   | Why We Chose It                     | What We Sacrificed        |
| -------------------------- | ----------------------------------- | ------------------------- |
| **State Pattern**          | Testable, reusable state logic      | Slightly more abstraction |
| **Interceptor Pattern**    | Clean separation, composable guards | Additional method calls   |
| \*\*Set-based O(1) lookups | Performance for large file counts   | Memory overhead (Sets)    |
| \*\*Rust Scanner for Tools | Fast tool discovery, type safety    | Rust dependency           |

---

## 8. Usage Examples

### Basic Execution

```python
from agent.core.omni import OmniLoop, run_sync

# Async usage
loop = OmniLoop()
result = await loop.run("Fix the login bug in auth.py", max_steps=4)

# Sync wrapper
result = run_sync("Add error handling to parser.py")
```

### Custom Configuration

```python
# With custom max steps
result = await loop.run("Refactor the entire module", max_steps=8)

# Access state after execution
loop.state.get_stats()
# {'visited_files': 3, 'modified_files': 1}
```

---

## 9. Performance Metrics

| Metric             | Before     | After     | Improvement      |
| ------------------ | ---------- | --------- | ---------------- |
| **Runtime**        | ~94s       | ~24s      | 74% faster       |
| **Tokens**         | ~60k       | ~7k       | 87% reduction    |
| **File Reads**     | 4+ repeats | 1-2 reads | No redundancy    |
| **Actions**        | 0 writes   | 1+ writes | Task completion  |
| **RAG Search**     | N/A        | ~50ms     | Semantic lookup  |
| **Knowledge Hits** | N/A        | 95%       | Context accuracy |

---

## 10. Future Roadmap

- [ ] Persistent state across sessions
- [ ] Multi-agent coordination support
- [ ] Custom guard implementations
- [ ] Performance profiling integration
- [ ] ML-based intent classification for RAG triggers
- [ ] Cross-session knowledge caching

---

## Related Documentation

- [Trinity Architecture](./system-layering.md) - System architecture overview
- [Context Orchestrator](../reference/mcp-orchestrator.md) - Layered context building
- [Skill Discovery](../llm/skill-discovery.md) - Dynamic skill loading
- [Librarian](../reference/librarian.md) - RAG knowledge retrieval
- [API Reference](../reference/cli.md) - OmniLoop CLI commands

---

_Built on standards. Not reinventing the wheel._
